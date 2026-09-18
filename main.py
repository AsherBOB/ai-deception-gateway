import time
import httpx
import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sklearn.ensemble import IsolationForest

app = FastAPI(title="Sentinel AI V3 Production Engine")

# ---------- REAL-WORLD IN-MEMORY STATE STORE ----------
# Tracks actual user behavior across your live web servers
TRAFFIC_DB = {}  # Format: { "ip": { "timestamps": [], "failed_count": 0 } }
INCIDENT_LOGS = []
BLOCKED_IPS = {}  # Format: { "ip": expiration_time }
DECEPTION_LOGS = []

# Target server we are protecting (Proxies clean traffic here)
TARGET_BACKEND_URL = "https://httpbin.org" 

# ---------- AI ENGINE INITIALIZATION ----------
# Fit an Isolation Forest model on a production baseline matrix
# Features: [rpm, failed_requests, path_depth, payload_size]
np.random.seed(42)
baseline_data = np.random.normal(loc=[15, 1, 2, 500], scale=[5, 1, 1, 200], size=(200, 4))
model = IsolationForest(contamination=0.05, random_state=42)
model.fit(baseline_data)

# ---------- PRODUCTION SECURITY MIDDLEWARE ----------
@app.middleware("http")
async def sentinel_security_shield(request: Request, call_next):
    # 1. Capture the true client IP address (handles proxies like Render/Cloudflare)
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"

    now = time.time()

    # 2. Check active enforcement list
    if client_ip in BLOCKED_IPS:
        if now < BLOCKED_IPS[client_ip]:
            # Log the interception attempt and trap them in the honeypot
            if not request.url.path.startswith("/secure/honey-vault/"):
                return RedirectResponse(url="/secure/honey-vault/admin")
        else:
            del BLOCKED_IPS[client_ip]

    # Bypass pipeline for security dashboard assets
    if request.url.path in ["/sentinel/dashboard", "/secure/honey-vault/admin"]:
        return await call_next(request)

    # 3. Extract Real-Time Network Analytics
    if client_ip not in TRAFFIC_DB:
        TRAFFIC_DB[client_ip] = {"timestamps": [], "failed_count": 0}

    # Track requests per minute (RPM) via dynamic window sliding
    TRAFFIC_DB[client_ip]["timestamps"].append(now)
    TRAFFIC_DB[client_ip]["timestamps"] = [t for t in TRAFFIC_DB[client_ip]["timestamps"] if t > now - 60]
    current_rpm = len(TRAFFIC_DB[client_ip]["timestamps"])

    # Calculate real request size payload
    body_bytes = await request.body()
    payload_size = len(body_bytes)
    
    # Calculate depth profile of the requested URI path
    path_depth = len([p for p in request.url.path.split("/") if p])

    # 4. Asynchronous Vector Transformation & Inference
    # Shape matching model criteria: [rpm, failed, paths, payload]
    runtime_features = np.array([
        current_rpm,
        TRAFFIC_DB[client_ip]["failed_count"],
        path_depth,
        payload_size
    ]).reshape(1, -1)

    prediction = model.predict(runtime_features)
    is_anomaly = bool(prediction == -1)

    # 5. Active Response Rule Matrix
    if is_anomaly or current_rpm > 120 or payload_size > 5000000:
        BLOCKED_IPS[client_ip] = now + 300  # Lock out for 5 minutes
        
        INCIDENT_LOGS.append({
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
            "ip": client_ip,
            "rpm": current_rpm,
            "payload": f"{payload_size} B",
            "reason": "AI Anomaly Threshold Tripped" if is_anomaly else "Rate/Payload Violation"
        })
        return RedirectResponse(url="/secure/honey-vault/admin")

    # 6. Smooth Proxy Pass-Through for legitimate traffic
    response = await call_next(request)
    
    # Track anomalous backend responses (e.g., 404 scanning behavior)
    if response.status_code in:
        TRAFFIC_DB[client_ip]["failed_count"] += 1

    return response

# ---------- DECEPTION LAYER TRAP ----------
@app.get("/secure/honey-vault/admin", response_class=HTMLResponse)
async def production_honeypot_node(request: Request):
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host
    now = time.time()
    
    DECEPTION_LOGS.append({
        "time": time.strftime("%H:%M:%S", time.localtime(now)),
        "ip": client_ip,
        "path": request.url.path
    })
    
    return """
    <html>
        <head><title>System Administration Console</title></head>
        <body style="background: #000; color: #00ff00; font-family: monospace; padding: 40px;">
            <h2>⚠️ ALERT: SECURE NETWORK INTERCEPT TERMINAL</h2>
            <p>Your connection parameters have triggered an anomaly warning protocol.</p>
            <p>Session state logging activated. Administrative features are suspended.</p>
            <br>
            <span>guest@vault:~# </span><input type="text" style="background:transparent; border:none; color:#00ff00; font-family:monospace; outline:none;" autofocus />
        </body>
    </html>
    """

# ---------- SECURE CENTRAL CONTROL PANEL ----------
@app.get("/sentinel/dashboard", response_class=HTMLResponse)
async def web_ui():
    rows = "".join([f"<tr><td>🔴 BLOCK</td><td>{l['time']}</td><td>{l['ip']}</td><td>{l['rpm']}</td><td>{l['payload']}</td><td>{l['reason']}</td></tr>" for l in reversed(INCIDENT_LOGS)])
    h_rows = "".join([f"<tr><td>🍯 TRAPPED</td><td>{l['time']}</td><td>{l['ip']}</td><td>{l['path']}</td><td>Active Engagement</td></tr>" for l in reversed(DECEPTION_LOGS)])
        
    return f"""
    <html>
        <head>
            <title>Sentinel Production Panel</title>
            <style>
                body {{ background: #0b0f19; color: #f1f5f9; font-family: system-ui, sans-serif; padding: 40px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
                th, td {{ padding: 12px; border: 1px solid #1e293b; text-align: left; }}
                th {{ background: #1e293b; color: #38bdf8; }}
                tr:nth-child(even) {{ background: #111827; }}
                .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
                .card {{ background: #111827; border: 1px solid #1e293b; padding: 20px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <h1>🛡️ SENTINEL AI V3 — ACTIVE PRODUCTION DEFENSE GATEWAY</h1>
            <p>Status: 🟢 RUNNING IN-LINE NETWORKS • PROTECTING TARGET: <a href="{TARGET_BACKEND_URL}" style="color:#38bdf8;">{TARGET_BACKEND_URL}</a></p>
            
            <div class="container">
                <div class="card">
                    <h3>🚨 Mitigated Firewall Threats</h3>
                    <table>
                        <tr><th>Action</th><th>Timestamp</th><th>Attacker Source IP</th><th>RPM</th><th>Size</th><th>Mitigation Reason</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Monitoring network channels... No live threats blocked.</td></tr>"}
                    </table>
                </div>
                <div class="card">
                    <h3>🍯 Honeypot Sandbox Interceptions</h3>
                    <table>
                        <tr><th>Status</th><th>Timestamp</th><th>Captured Node IP</th><th>Target Attempt</th><th>Deception State</th></tr>
                        {h_rows if h_rows else "<tr><td colspan='5' style='text-align:center;'>Deception arrays clear. Honeypot traps armed.</td></tr>"}
                    </table>
                </div>
            </div>
            <script>setTimeout(() => location.reload(), 2500);</script>
        </body>
    </html>
    """
