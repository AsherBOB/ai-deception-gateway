import os
import numpy as np
import time
from fastapi import FastAPI, Request
from sentence_transformers import SentenceTransformer

# Initialize the production model globally so it stays warm in memory
print("🤖 Loading production Transformer Model (all-MiniLM-L6-v2)...")
ai_model = SentenceTransformer('all-MiniLM-L6-v2')

# High-fidelity anchors representing hostile attack definitions
threat_intents = [
    "sql injection select union authentication bypass drop table",
    "directory traversal system file access path escape etc passwd",
    "remote code execution reverse shell memory exploit payload execution"
]
threat_embeddings = ai_model.encode(threat_intents)

app = FastAPI(title="AI Cyber Deception Gateway")

# Simulated backends
PRODUCTION_DB = {"status": "success", "environment": "PRODUCTION_SECURE", "data": "Corporate Revenue: $42,000,000"}
HONEYPOT_DECOY = {"status": "success", "environment": "PRODUCTION_SECURE", "data": "Corporate Revenue: $14,250"}

@app.post("/v1/secure-ingress")
async def inbound_proxy_gateway(request: Request):
    body_bytes = await request.body()
    payload_string = body_bytes.decode("utf-8")
    client_ip = request.client.host if request.client else "Unknown IP"
    
    if not payload_string.strip():
        return PRODUCTION_DB

    # 1. AI Engine Vector Calculation
    payload_embedding = ai_model.encode([payload_string])
    similarities = []
    for threat_emb in threat_embeddings:
        dot_prod = np.dot(payload_embedding, threat_emb)
        norm_a = np.linalg.norm(payload_embedding)
        norm_b = np.linalg.norm(threat_emb)
        similarity = dot_prod / (norm_a * norm_b)
        similarities.append(similarity)
    
    threat_score = float(max(similarities))
    
    # 2. Deception Shunting Logic
    if threat_score >= 0.38:
        print(f"⚠️ [DECEPTION TRIGGERED] Threat: {threat_score:.4f} | IP: {client_ip} | Payload: {payload_string}")
        # Artificially delay connection to consume attacker resources
        time.sleep(0.5) 
        return HONEYPOT_DECOY
        
    return PRODUCTION_DB

# Simple healthcheck endpoint for Render to verify the application is alive
@app.get("/")
def health_check():
    return {"status": "healthy", "service": "AI Cyber Deception Gateway"}
