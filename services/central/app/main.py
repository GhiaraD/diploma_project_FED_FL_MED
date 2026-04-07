from fastapi import FastAPI
import os

app = FastAPI(title="Central FL", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/round/current")
def round_current():
    # placeholder: in MVP vei returna planul rundei
    return {"round_id": "R-0", "status": "placeholder"}

@app.get("/model/latest")
def model_latest():
    # placeholder: in MVP vei servi weights.pt
    return {"model_id": "W-0", "status": "placeholder"}

@app.post("/update")
def submit_update():
    # placeholder: in MVP vei primi delta.pt + metadata
    return {"ok": True, "status": "placeholder"}