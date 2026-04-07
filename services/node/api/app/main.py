from fastapi import FastAPI
import os

app = FastAPI(title="Node API", version="0.1.0")

@app.get("/api/health")
def health():
    return {"ok": True, "node_id": os.getenv("NODE_ID", "unknown")}

@app.get("/api/node/status")
def node_status():
    return {
        "node_id": os.getenv("NODE_ID", "unknown"),
        "storage_root": os.getenv("STORAGE_ROOT", "/storage"),
        "central_url": os.getenv("CENTRAL_URL", ""),
    }

@app.post("/api/infer")
def infer():
    # placeholder: va porni job in worker
    return {"job_id": "infer-placeholder"}

@app.post("/api/train")
def train():
    # placeholder: va porni job in worker
    return {"job_id": "train-placeholder"}