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
from pydantic import BaseModel

# Add src/ to the Python path so we can import modules from it
import sys
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
ALERTS_JSON = "outputs/alerts.json"
STATION_META_CSV = "data/station_metadata.csv"
OBSERVATIONS_CSV = "data/test_injected_aws.csv"

MAX_OBSERVATIONS = 2000


# ----------------------------------------------------------------------
# Startup: auto-clean demo alerts from alerts.json
# ----------------------------------------------------------------------
try:
    if os.path.exists("outputs/alerts.json"):
        with open("outputs/alerts.json", "r") as f:
            _alerts = json.load(f)
        _clean = [a for a in _alerts if not a.get("_demo", False)]
        if len(_clean) != len(_alerts):
            with open("outputs/alerts.json", "w") as f:
                json.dump(_clean, f, indent=2, default=str)
            print(f"[startup] Cleaned {len(_alerts) - len(_clean)} demo alerts")
        else:
            print(f"[startup] {len(_clean)} alerts loaded (no demo alerts)")
except Exception as e:
    print(f"[startup] Warning: could not clean demo alerts: {e}")


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
# In-memory store for injected alerts (persists for process lifetime; works on ephemeral filesystems like Railway)
_injected_alerts = []



def _read_alerts() -> list:
    if not os.path.exists(ALERTS_JSON):
        raise HTTPException(
            status_code=404,
            detail=f"Alerts file not found: {ALERTS_JSON}. Run the pipeline first."
        )
    with open(ALERTS_JSON, "r", encoding="utf-8") as f:
        alerts = json.load(f)
    # Merge in-memory injected alerts with file-based alerts (ephemeral-fs safe)
    combined = _injected_alerts + alerts
    # In production (DEMO_MODE unset), hide demo alerts from API responses.
    # Set DEMO_MODE=true for local demo to see injected alerts on the Dashboard.
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    if demo_mode:
        return combined
    return [a for a in combined if not a.get("_demo", False)]


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
# ----------------------------------------------------------------------
# Fault Injection (demo)
# ----------------------------------------------------------------------
class InjectionRequest(BaseModel):
    station_id: str
    fault_type: str
    magnitude: float | None = None


@app.get("/api/injection-fault-types")
def get_fault_types():
    """List available fault types for the injection lab."""
    from inject_demo import FAULT_TYPES, DEFAULT_MAGNITUDE
    return {
        "fault_types": FAULT_TYPES,
        "default_magnitudes": DEFAULT_MAGNITUDE,
    }


# Cache the fast injection helper so it's built once per process.
_fast_injector = None


def _get_fast_injector():
    global _fast_injector
    if _fast_injector is None:
        from inject_demo_fast import FastInjector
        _fast_injector = FastInjector()
    return _fast_injector


@app.post("/api/inject")
def inject_fault(req: InjectionRequest):
    """
    Inject a synthetic fault and run detection.
    Uses a pre-computed pipeline baseline for speed.
    """
    try:
        injector = _get_fast_injector()
        result = injector.inject(
            station_id=req.station_id,
            fault_type=req.fault_type,
            magnitude=req.magnitude,
        )
        # ---- Add to in-memory store (works on ephemeral filesystems like Railway) ----
        if isinstance(result, dict) and "alert" in result:
            _injected_alerts.insert(0, result["alert"])
        # ---- Also try to write to file (persists locally) ----
        try:
            import json
            alerts_path = "outputs/alerts.json"
            if os.path.exists(alerts_path):
                with open(alerts_path, "r") as f:
                    existing = json.load(f)
                existing.insert(0, result["alert"])
                with open(alerts_path, "w") as f:
                    json.dump(existing, f, indent=2, default=str)
        except Exception as e:
            print(f"[inject] Could not persist to file: {e}")
        # ----------------------------------------------------------------------
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/reality-check")
def reality_check():
    """
    Run two contrasting scenarios:
    A) Isolated sensor fault — one station spikes, neighbors normal
    B) Regional weather event — all stations rise together
    """
    try:
        from inject_demo import build_comparison_scenarios
        return build_comparison_scenarios()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)