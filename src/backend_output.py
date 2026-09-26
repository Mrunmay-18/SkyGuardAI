"""
src/backend_output.py
SkyGuard AI — STEP 22: Final backend output.

Converts the final outputs of Steps 17–21 into a clean, frontend-friendly
JSON structure (one object per detected anomaly). No ML here — pure
formatting and joining.

Reads:
    - scored DataFrame (from classify_anomalies + score_anomalies + explain_dataframe)
    - sensor health DataFrame (from calculate_sensor_health)

Writes:
    - outputs/alerts.json  (list of dicts, one per anomaly)
"""

import json
import os
import sys

import pandas as pd


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
OUTPUT_DIR = "outputs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "alerts.json")

# Sensor health normalization (from the plan).
HEALTH_MAP = {
    "Healthy": "healthy",
    "Watch": "watch",
    "At Risk": "at_risk",
}

# Columns that must exist in the scored DataFrame for backend output.
REQUIRED_COLUMNS = [
    "station_id",
    "timestamp",
    "temperature",
    "pressure",
    "humidity",
    "anomaly_class",
    "anomaly_confidence",
    "severity",
    "explanation",
]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _safe_float(value):
    """Return float or None if not convertible."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    """Return int or None if not convertible."""
    try:
        if pd.isna(value):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _row_is_anomaly(row) -> bool:
    """
    A row is an anomaly if the fused evidence layer says so.

    Uses fused_any_flag (Step 17 output), which requires
    corroborating evidence from multiple detectors. Falls back
    to the raw union ONLY if fused_any_flag is missing.
    """
    # Preferred: use the fusion decision.
    if "fused_any_flag" in row.index:
        try:
            return int(row["fused_any_flag"]) == 1
        except (TypeError, ValueError):
            pass

    # Fallback: raw union (only if fusion output is missing).
    flags = [
        "predicted_anomaly",
        "qc_any_flag",
        "temporal_predicted_anomaly",
        "spatial_any_flag",
        "spatial_isolated_flag",
    ]
    for f in flags:
        if f in row.index:
            try:
                if int(row[f]) == 1:
                    return True
            except (TypeError, ValueError):
                pass
    return False


def _build_reasons(row) -> list:
    """
    Extract only the actual reasons from the Step 19 explanation.

    The explainer produces a structured block like:

        === Anomaly Explanation ===
        Station: AWS_05
        ...
        Reasons:
        - <reason 1>
        - <reason 2>
        Recommendation:
        <recommendation text>

    We keep ONLY the lines between 'Reasons:' and 'Recommendation:'.
    Station, timestamp, confidence, severity, and recommendation
    already have dedicated JSON fields, so they must not appear here.
    """
    raw = row.get("explanation", "")

    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []

    text = str(raw).strip()

    if not text:
        return []

    lines = text.splitlines()

    reasons = []
    in_reasons = False

    for line in lines:
        line = line.strip()

        if line.lower() == "reasons:":
            in_reasons = True
            continue

        if line.lower() == "recommendation:":
            break

        if in_reasons and line:
            cleaned = line.lstrip("-•\t ").strip()
            if cleaned:
                reasons.append(cleaned)

    return reasons
# ----------------------------------------------------------------------
# Corrected value estimation (self-healing)
# ----------------------------------------------------------------------
def _compute_corrected_values(
    row,
    meta: "pd.DataFrame",
    obs_df: "pd.DataFrame",
) -> dict:
    """
    Estimate corrected T/P/H for an anomalous reading using the median
    of neighbouring stations at the same timestamp.

    Returns a dict with:
        corrected_temperature, corrected_pressure, corrected_humidity,
        correction_confidence (0-100 or None),
        correction_basis (string describing how it was computed)

    If neighbours cannot be determined (missing metadata, no valid
    neighbour reading at this timestamp), returns empty values with a
    basis note explaining why.
    """
    empty = {
        "corrected_temperature": None,
        "corrected_pressure": None,
        "corrected_humidity": None,
        "correction_confidence": None,
        "correction_basis": "not available",
    }

    station_id = row.get("station_id")
    ts = row.get("timestamp")
    if station_id is None or ts is None:
        return empty

    # Find neighbours (all other stations within 100 km, simple fallback).
    if station_id not in meta["station_id"].values:
        return empty
    me = meta[meta["station_id"] == station_id].iloc[0]
    others = meta[meta["station_id"] != station_id].copy()

    # Haversine distance (km)
    import numpy as np
    R = 6371.0088
    lat1, lon1 = np.radians(me["latitude"]), np.radians(me["longitude"])
    lat2 = np.radians(others["latitude"].to_numpy())
    lon2 = np.radians(others["longitude"].to_numpy())
    dphi = lat2 - lat1
    dlam = lon2 - lon1
    a = np.sin(dphi / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlam / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    others["distance_km"] = R * c

    # Keep 2 nearest neighbours within 100 km.
    neighbours = others[others["distance_km"] <= 100.0].nsmallest(2, "distance_km")
    if len(neighbours) == 0:
        return empty

    # Find their readings at the same timestamp.
    ts_str = str(ts)
    neighbour_ids = neighbours["station_id"].tolist()
    same_ts = obs_df[
        (obs_df["timestamp"].astype(str) == ts_str)
        & (obs_df["station_id"].isin(neighbour_ids))
    ]

    if len(same_ts) == 0:
        return {
            **empty,
            "correction_basis": "no neighbour reading at this timestamp",
        }

    t_med = same_ts["temperature"].median() if same_ts["temperature"].notna().any() else None
    p_med = same_ts["pressure"].median() if same_ts["pressure"].notna().any() else None
    h_med = same_ts["humidity"].median() if same_ts["humidity"].notna().any() else None

    # Confidence: higher when neighbours agree tightly.
    # Uses 1 - (std / mean) heuristic, clamped to 50-95.
    def _agreement_conf(series):
        if series.dropna().empty or len(series.dropna()) < 2:
            return 70  # only one neighbour → moderate
        vals = series.dropna()
        if vals.mean() == 0:
            return 70
        spread = float(vals.std() / abs(vals.mean()))
        conf = max(50, min(95, int(95 - spread * 500)))
        return conf

    conf_t = _agreement_conf(same_ts["temperature"])
    conf_p = _agreement_conf(same_ts["pressure"])
    conf_h = _agreement_conf(same_ts["humidity"])
    correction_confidence = int((conf_t + conf_p + conf_h) / 3)

    neighbour_str = ", ".join(neighbour_ids[:2])
    return {
        "corrected_temperature": round(float(t_med), 2) if t_med is not None else None,
        "corrected_pressure": round(float(p_med), 2) if p_med is not None else None,
        "corrected_humidity": round(float(h_med), 2) if h_med is not None else None,
        "correction_confidence": correction_confidence,
        "correction_basis": f"median of {len(same_ts)} neighbouring station(s) ({neighbour_str})",
    }

# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def build_backend_output(
    scored_df: pd.DataFrame,
    health_df: pd.DataFrame,
    meta_df: pd.DataFrame = None,
    obs_df: pd.DataFrame = None,
) -> list:
    """
    Build a clean list of alert dicts from scored + health DataFrames.

    Parameters
    ----------
    scored_df : pd.DataFrame
        Output of explain_dataframe(score_anomalies(classify_anomalies(...)))
        Must contain the columns listed in REQUIRED_COLUMNS.
    health_df : pd.DataFrame
        Output of calculate_sensor_health(scored_df).
        Must contain: station_id, maintenance_status, maintenance_recommendation.

    Returns
    -------
    list of dict
        One dict per anomaly row, ready for JSON serialization.
    """    # Fallback if caller didn't provide metadata / observations.
    if meta_df is None:
        meta_df = pd.read_csv("data/station_metadata.csv")
    if obs_df is None:
        obs_df = pd.read_csv("data/test_injected_aws.csv")
        obs_df["timestamp"] = pd.to_datetime(obs_df["timestamp"])

  
    # Validate required columns.
    
    missing = [c for c in REQUIRED_COLUMNS if c not in scored_df.columns]
    if missing:
        raise ValueError(
            f"scored_df is missing required columns: {missing}. "
            f"Available: {list(scored_df.columns)}"
        )

    if "station_id" not in health_df.columns:
        raise ValueError(
            "health_df must contain 'station_id'. "
            f"Available: {list(health_df.columns)}"
        )

    # Build a per-station lookup of health info.
    health_lookup = {}
    for _, h in health_df.iterrows():
        sid = h["station_id"]
        health_lookup[sid] = {
            "sensor_health": HEALTH_MAP.get(
                str(h.get("maintenance_status", "")).strip(),
                "unknown",
            ),
            "maintenance_recommendation": str(
                h.get("maintenance_recommendation", "")
            ).strip(),
        }

    # Emit one alert per anomaly row.
    alerts = []
    for _, row in scored_df.iterrows():
        if not _row_is_anomaly(row):
            continue

        sid = str(row["station_id"])
        health_info = health_lookup.get(
            sid,
            {"sensor_health": "unknown", "maintenance_recommendation": ""},
        )

        # Compute self-healing corrected values using neighbours.
        corrected = _compute_corrected_values(row, meta_df, obs_df)

        alert = {
            "station_id": sid,
            "timestamp": str(row["timestamp"]),
            "temperature": _safe_float(row.get("temperature")),
            "pressure": _safe_float(row.get("pressure")),
            "humidity": _safe_float(row.get("humidity")),
            "status": "anomaly",
            "anomaly_type": str(row.get("anomaly_class", "Unknown")),
            "confidence": _safe_int(row.get("anomaly_confidence")),
            "severity": str(row.get("severity", "Unknown")),
            "reasons": _build_reasons(row),
            "sensor_health": health_info["sensor_health"],
            "maintenance_recommendation": health_info["maintenance_recommendation"],
            "corrected_temperature": corrected["corrected_temperature"],
            "corrected_pressure": corrected["corrected_pressure"],
            "corrected_humidity": corrected["corrected_humidity"],
            "correction_confidence": corrected["correction_confidence"],
            "correction_basis": corrected["correction_basis"],
        }
        alerts.append(alert)
    return alerts


def save_alerts(alerts: list, path: str = OUTPUT_FILE) -> str:
    """Write alerts list to JSON. Returns the path written."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, default=str)
    return path


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)

    from feature_engineering import build_features
    from qc_rules import apply_qc_rules
    from spatial_analysis import apply_spatial_analysis
    from temporal_detector import apply_temporal_detector
    from anomaly_classifier import classify_anomalies
    from scoring import score_anomalies
    from explainer import explain_dataframe
    from sensor_health import calculate_sensor_health

    print("=" * 60)
    print("SkyGuard AI — Backend Output Demo")
    print("=" * 60)

    # 1. Load test data.
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])

    # 2. Features + QC.
    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()

    # 3. Spatial.
    metadata = pd.read_csv("data/station_metadata.csv")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spatial = apply_spatial_analysis(obs, metadata)
    spatial_cols = ["station_id", "timestamp"] + [
        c for c in spatial.columns if c.startswith("spatial_")
    ]
    spatial = spatial[spatial_cols].copy()

    # 4. Temporal.
    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()

    # 5. Isolation Forest predictions.
    if_df = pd.read_csv("data/isolation_forest_predictions.csv")
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()

    # 6. Merge all evidence (drop duplicate ground-truth cols from IF file).
    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(spatial, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(temporal, on=["station_id", "timestamp"], how="left")

    classified = classify_anomalies(joined)
    scored = score_anomalies(classified)

    # Run the fusion layer to get fused_any_flag.
    from evidence_fusion import fuse_evidence
    fused = fuse_evidence(scored)

    explained = explain_dataframe(fused)
    health = calculate_sensor_health(explained)

    # 9. Build backend output.
    alerts = build_backend_output(explained, health, meta_df=metadata, obs_df=obs)

    # 10. Save + print.
    path = save_alerts(alerts)
    print(f"\nTotal anomalies: {len(alerts)}")
    print(f"Saved to: {path}\n")
    print("First 5 alerts (pretty-printed):\n")
    for a in alerts[:5]:
        print(json.dumps(a, indent=2, default=str))
        print("-" * 60)