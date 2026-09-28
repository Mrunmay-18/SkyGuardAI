"""
api.py
SkyGuard AI — FastAPI backend.

Reads the frozen pipeline output (outputs/alerts.json, data/*.csv) and
exposes it via REST endpoints for the React frontend.
"""

import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
ALERTS_JSON = "outputs/alerts.json"
STATION_META_CSV = "data/station_metadata.csv"
OBSERVATIONS_CSV = "data/test_injected_aws.csv"

MAX_OBSERVATIONS = 2000


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
app = FastAPI(title="SkyGuard AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _read_alerts() -> list:
    if not os.path.exists(ALERTS_JSON):
        raise HTTPException(
            status_code=404,
            detail=f"Alerts file not found: {ALERTS_JSON}. Run the pipeline first."
        )
    with open(ALERTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_stations() -> pd.DataFrame:
    if not os.path.exists(STATION_META_CSV):
        raise HTTPException(status_code=404, detail=f"Missing: {STATION_META_CSV}")
    return pd.read_csv(STATION_META_CSV)


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "SkyGuard AI API"}


@app.get("/api/alerts")
def get_alerts():
    return _read_alerts()


@app.get("/api/alerts/{station_id}")
def get_alerts_by_station(station_id: str):
    alerts = _read_alerts()
    return [a for a in alerts if a.get("station_id") == station_id]


@app.get("/api/stations")
def get_stations():
    df = _read_stations()
    return df.to_dict(orient="records")


@app.get("/api/observations")
def get_observations(limit: int = MAX_OBSERVATIONS):
    if not os.path.exists(OBSERVATIONS_CSV):
        raise HTTPException(status_code=404, detail=f"Missing: {OBSERVATIONS_CSV}")
    df = pd.read_csv(OBSERVATIONS_CSV)
    df = df.tail(min(limit, MAX_OBSERVATIONS))
    return df.to_dict(orient="records")


@app.get("/api/observations/{station_id}")
def get_observations_by_station(station_id: str, limit: int = 500):
    if not os.path.exists(OBSERVATIONS_CSV):
        raise HTTPException(status_code=404, detail=f"Missing: {OBSERVATIONS_CSV}")
    df = pd.read_csv(OBSERVATIONS_CSV)
    df = df[df["station_id"] == station_id].tail(min(limit, MAX_OBSERVATIONS))
    return df.to_dict(orient="records")


# ----------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)