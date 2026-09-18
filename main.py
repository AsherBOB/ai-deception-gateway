import time
import random
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import numpy as np
from sklearn.ensemble import IsolationForest

app = FastAPI(title="Sentinel AI V3 Production Engine")

# ---------- IN-MEMORY STATE STORAGE ----------
TRAFFIC_DB = {}
INCIDENT_LOGS = []
BLOCKED_IPS = {} # Structure: { "ip": expiration_timestamp }
DECEPTION_LOGS = []

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
    
    if ip not in TRAFFIC_DB:
        TRAFFIC_DB[ip] = {"timestamps": [], "total_payload": 0, "failed_count": 0}
        
    TRAFFIC_DB[ip]["timestamps"].append(now)
    TRAFFIC_DB[ip]["timestamps"] = [t for t in TRAFFIC_DB[ip]["timestamps"] if t > now - 60]
    current_rpm = len(TRAFFIC_DB[ip]["timestamps"])
    
    TRAFFIC_DB[ip]["total_payload"] += data.payload_size
    if data.is_failed:
        TRAFFIC_DB[ip]["failed_count"] += 1
        
    extracted_features = np.array([
        current_rpm,
        TRAFFIC_DB[ip]["failed_count"],
        data.path_depth,
        data.payload_size,
        45,
        0,
        current_rpm // 3
    ]).reshape(1, -1)
    
    prediction = model.predict(extracted_features)
    is_threat = bool(prediction == -1)
    
    action = "ALLOWED"
    if is_threat:
        action = "CONTAINED"
        BLOCKED_IPS[ip] = now + 600 # Block/Divert for 10 minutes
        
        log_entry = {
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
            "ip": ip,
            "rpm": current_rpm,
            "payload": data.payload_size,
            "action": "DIVERTED_TO_HONEYPOT"
        }
        INCIDENT_LOGS.append(log_entry)
        if len(INCIDENT_LOGS) > 20:
            INCIDENT_LOGS.pop(0)
            
    return {
        "status": "success",
        "ip": ip,
        "ai_analysis": {"is_threat": is_threat, "action": action}
    }

# ---------- MIDDLEWARE INTERCEPTION BLOCK ----------
@app.middleware("http")
async def check_deception_layer(request: Request, call_next):
    # Retrieve client IP address
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Check if this specific user IP is locked in the active containment pool
    if client_ip in BLOCKED_IPS:
        if now < BLOCKED_IPS[client_ip]:
            # If the attacker tries to hit our production UI homepage, silently trap them in the Honeypot endpoint instead!
            if request.url.path == "/":
                return RedirectResponse(url="/secure/honey-vault/admin")
        else:
            del BLOCKED_IPS[client_ip] # Block expired
            
    response = await call_next(request)
    return response

# ---------- DECEPTION LAYER (HONEYPOT VAULT) ----------
@app.get("/secure/honey-vault/admin", response_class=HTMLResponse)
async def production_honeypot_node(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    decoy_services = ["Fake Root Cluster", "Primary Shadow Database", "Encrypted Credentials File"]
    decoy_actions = ["Brute force flag triggered", "Directory index list attempted", "SQL Dump query intercepted"]
    
    h_entry = {
        "time": time.strftime("%H:%M:%S", time.localtime(now)),
        "ip": client_ip,
        "service": random.choice(decoy_services),
        "activity": random.choice(decoy_actions)
    }
    DECEPTION_LOGS.append(h_entry)
    
    return f"""
    <html>
        <head>
            <title>Internal Core Console</title>
            <style>
                body {{ background: #000; color: #33ff33; font-family: monospace; padding: 50px; }}
                .terminal {{ border: 2px solid #33ff33; padding: 20px; background: #050505; box-shadow: 0 0 15px rgba(51,255,51,0.4); }}
                input {{ background: transparent; border: none; color: #33ff33; font-family: monospace; width: 80%; outline: none; }}
            </style>
        </head>
        <body>
            <div class="terminal">
                <h2>⚠️ WARNING: SECURE ENVIRONMENT NODE</h2>
                <p>SESSION ID: MOCK-DECOY-{random.randint(10000, 99999)}</p>
                <p>Loading database structures... DONE.</p>
                <p>Target System: [Production_Cluster_Alpha]</p>
                <br>
                <div>root@admin:~# <input type="text" value="cat config.json" disabled /></div>
                <p style="color: red;">[ACCESS ERROR]: High-privilege tokens locked. Verification required.</p>
            </div>
        </body>
    </html>
    """

# ---------- MANAGEMENT CONTROL BOARD ----------
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    rows = "".join([f"<tr><td>🔴</td><td>{l['time']}</td><td>{l['ip']}</td><td>{l['rpm']}</td><td>{l['payload']} B</td><td>{l['action']}</td></tr>" for l in reversed(INCIDENT_LOGS)])
    h_rows = "".join([f"<tr><td>🍯</td><td>{l['time']}</td><td>{l['ip']}</td><td>{l['service']}</td><td>{l['activity']}</td></tr>" for l in reversed(DECEPTION_LOGS)])
        
    return f"""
    <html>
        <head>
            <title>Sentinel AI V3 Controller</title>
            <style>
                body {{ background: #071018; color: white; font-family: sans-serif; padding: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
                th, td {{ padding: 10px; border: 1px solid #23404d; text-align: left; }}
                th {{ background: #102230; color: #6bb9e8; }}
                .grid {{ display: flex; gap: 20px; }}
                .col {{ flex: 1; }}
            </style>
        </head>
        <body>
            <h1>🛡️ SENTINEL AI V3 — ADVANCED DEFENSE PANEL</h1>
            <p>Active Status: 🟢 CORE ACTIVE • ENGINE MONITORING EDGE</p>
            
            <div class="grid">
                <div class="col">
                    <h3>🚨 Incident Mitigation Logs</h3>
                    <table>
                        <tr><th>Status</th><th>Time</th><th>Source IP</th><th>RPM</th><th>Payload</th><th>Action Taking</th></tr>
                        {rows if rows else "<tr><td colspan='6'>Monitoring telemetry incoming webhooks...</td></tr>"}
                    </table>
                </div>
                <div class="col">
                    <h3>🍯 Live Deception Honeypot Engagements</h3>
                    <table>
                        <tr><th>Type</th><th>Time</th><th>Attacker IP</th><th>Decoy Service Asset</th><th>Interception Detail</th></tr>
                        {h_rows if h_rows else "<tr><td colspan='5'>Waiting for attackers to hit the honeypot snare...</td></tr>"}
                    </table>
                </div>
            </div>
            <script>setTimeout(() => location.reload(), 3000);</script>
        </body>
    </html>
    """
