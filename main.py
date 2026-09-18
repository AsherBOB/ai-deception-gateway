import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLMock, HTMLResponse
from pydantic import BaseModel
import numpy as np
from sklearn.ensemble import IsolationForest

app = FastAPI(title="Sentinel AI V3 Production Engine")

# ---------- IN-MEMORY STATE STORAGE ----------
# Tracks user activity data directly in server RAM memory
TRAFFIC_DB = {}  # Format: { "ip_address": { "timestamps": [...], "total_payload": 0, "failed_count": 0 } }
INCIDENT_LOGS = []

# ---------- AI MODEL BASELINE ----------
np.random.seed(42)
training_matrix = np.random.normal(50, 15, (100, 7))
model = IsolationForest(contamination=0.08, random_state=42)
model.fit(training_matrix)

class TelemetryPayload(BaseModel):
    ip: str
    payload_size: int
    is_failed: bool = False
    path_depth: int = 1

# ---------- CORE AI TELEMETRY ENGINE ----------
@app.post("/api/v3/telemetry")
async def process_telemetry(data: TelemetryPayload):
    ip = data.ip
    now = time.time()
    
    # Initialize state tracking variables if IP is new
    if ip not in TRAFFIC_DB:
        TRAFFIC_DB[ip] = {"timestamps": [], "total_payload": 0, "failed_count": 0}
        
    # 1. Slide window algorithm to calculate real-time Requests Per Minute (RPM)
    TRAFFIC_DB[ip]["timestamps"].append(now)
    TRAFFIC_DB[ip]["timestamps"] = [t for t in TRAFFIC_DB[ip]["timestamps"] if t > now - 60]
    current_rpm = len(TRAFFIC_DB[ip]["timestamps"])
    
    # 2. Track cumulative traffic markers
    TRAFFIC_DB[ip]["total_payload"] += data.payload_size
    if data.is_failed:
        TRAFFIC_DB[ip]["failed_count"] += 1
        
    # 3. Shape real-time features for the AI Isolation Forest 
    extracted_features = np.array([
        current_rpm,
        TRAFFIC_DB[ip]["failed_count"],
        data.path_depth,
        data.payload_size,
        45,               # Duration constant placeholder
        0,                # Privilege baseline value
        current_rpm // 3  # Calculated data payload bursts
    ]).reshape(1, -1)
    
    # 4. Predict anomaly threat probability
    prediction = model.predict(extracted_features)
    is_threat = bool(prediction == -1)
    
    action = "ALLOWED"
    if is_threat:
        action = "CONTAINED"
        log_entry = {
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
            "ip": ip,
            "rpm": current_rpm,
            "payload": data.payload_size,
            "action": action
        }
        INCIDENT_LOGS.append(log_entry)
        if len(INCIDENT_LOGS) > 20:  # Prevent memory leaks
            INCIDENT_LOGS.pop(0)
            
    return {
        "status": "success",
        "ip": ip,
        "metrics": {"rpm": current_rpm, "payload": data.payload_size},
        "ai_analysis": {"is_threat": is_threat, "action": action}
    }

# ---------- DASHBOARD FRONTEND ----------
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    rows = ""
    for log in reversed(INCIDENT_LOGS):
        rows += f"<tr><td>🔴</td><td>{log['time']}</td><td>{log['ip']}</td><td>{log['rpm']}</td><td>{log['payload']} B</td><td>{log['action']}</td></tr>"
        
    return f"""
    <html>
        <head>
            <title>Sentinel AI V3 Dashboard</title>
            <style>
                body {{ background: #071018; color: white; font-family: sans-serif; padding: 40px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; border: 1px solid #23404d; text-align: left; }}
                th {{ background: #102230; }}
            </style>
        </head>
        <body>
            <h1>🛡️ SENTINEL AI V3 — LIVE PRODUCTION LOGS</h1>
            <p>Status: 🟢 ONLINE & MONITORING REAL TRAFFIC</p>
            <table>
                <tr><th>Status</th><th>Time</th><th>Source IP</th><th>RPM</th><th>Payload Size</th><th>Action Taking</th></tr>
                {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Waiting for incoming server telemetry webhooks...</td></tr>"}
            </table>
            <script>setTimeout(() => location.reload(), 3000);</script>
        </body>
    </html>
    """
