"""
src/inject_demo.py
SkyGuard AI — Fault Injection Lab (demo backend, Option B).

Runs the REAL frozen pipeline on a synthetic injected fault so the demo
shows actual detection output (evidence, reasoning, trust, corrected values).

CRITICAL: This module does NOT modify any existing pipeline file. It only
imports from them. It never writes to outputs/alerts.json or any CSV.
"""

import copy
import os
import sys
from datetime import datetime
from typing import Optional

import pandas as pd


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
OBS_CSV = "data/test_injected_aws.csv"
META_CSV = "data/station_metadata.csv"

FAULT_TYPES = [
    "temperature_spike",
    "temperature_drop",
    "frozen_sensor",
    "humidity_spike",
    "pressure_drop",
    "total_collapse",
]

DEFAULT_MAGNITUDE = {
    "temperature_spike": 15.0,
    "temperature_drop": 12.0,
    "frozen_sensor": 0.0,
    "humidity_spike": 30.0,
    "pressure_drop": 20.0,
    "total_collapse": 0.0,
}


# ----------------------------------------------------------------------
# Sibling import shim
# ----------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


# ----------------------------------------------------------------------
# Fault application
# ----------------------------------------------------------------------
def _apply_fault(row: pd.Series, fault_type: str, magnitude: float) -> pd.Series:
    """Apply a synthetic fault to a copy of a single observation row."""
    modified = row.copy()

    if fault_type == "temperature_spike":
        modified["temperature"] = round(float(row["temperature"]) + magnitude, 2)

    elif fault_type == "temperature_drop":
        mag = abs(magnitude)
        modified["temperature"] = round(float(row["temperature"]) - mag, 2)

    elif fault_type == "frozen_sensor":
        # Simulate frozen sensor by copying the PREVIOUS row's temperature.
        # Handled by the caller (uses df.iloc[-2]).
        pass

    elif fault_type == "humidity_spike":
        modified["humidity"] = round(float(row["humidity"]) + magnitude, 2)

    elif fault_type == "pressure_drop":
        mag = abs(magnitude)
        modified["pressure"] = round(float(row["pressure"]) - mag, 2)

    elif fault_type == "total_collapse":
        modified["temperature"] = 0.0
        modified["pressure"] = 0.0
        modified["humidity"] = 0.0

    return modified


# ----------------------------------------------------------------------
# Full pipeline on injected row
# ----------------------------------------------------------------------
def _run_pipeline_on_injection(
    station_id: str,
    fault_type: str,
    magnitude: float,
) -> dict:
    """
    Run the real frozen pipeline on the last 96 rows of a station with
    the final row modified by the injected fault.

    Returns a structured result with the alert for the last row.
    """
    from feature_engineering import build_features
    from qc_rules import apply_qc_rules
    from spatial_analysis import apply_spatial_analysis
    from temporal_detector import apply_temporal_detector
    from anomaly_classifier import classify_anomalies
    from scoring import score_anomalies
    from evidence_fusion import fuse_evidence
    from backend_output import (
        _compute_priority,
        _compute_evidence_breakdown,
        _compute_counter_reasoning,
        _compute_trust_score,
        _compute_event_class,
        _compute_physical_reasoning,
        _compute_multivariate_analysis,
        _compute_genuine_weather_verdict,
        _compute_defensibility,
    )

    if not os.path.exists(OBS_CSV):
        raise FileNotFoundError(f"Missing: {OBS_CSV}")

    full_df = pd.read_csv(OBS_CSV)
    full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])

    # Extract last 96 rows of this station
    station_df = full_df[full_df["station_id"] == station_id].copy()
    if station_df.empty:
        raise ValueError(f"Unknown station_id: {station_id}")

    station_df = station_df.sort_values("timestamp").reset_index(drop=True)
    if len(station_df) < 2:
        raise ValueError(f"Not enough readings for station {station_id}")

    # Take the last 96 rows (24h at 15-min cadence) for context
    context = station_df.tail(96).copy()
    last_idx = context.index[-1]

    original_row = context.loc[last_idx].copy()

    # Apply fault
    if fault_type == "frozen_sensor":
        # Simulate a stuck sensor: freeze the last 24 readings to a single value
        # taken from ~6 hours ago. This triggers the QC persistence rule.
        freeze_val = float(context.loc[context.index[-24], "temperature"]) if len(context) >= 24 else float(context.loc[context.index[0], "temperature"])
        for i in range(max(0, len(context) - 24), len(context)):
            context.loc[context.index[i], "temperature"] = freeze_val
    else:
        modified_row = _apply_fault(original_row, fault_type, magnitude)
        for col in ["temperature", "pressure", "humidity"]:
            context.loc[last_idx, col] = modified_row[col]

    modified_row = context.loc[last_idx].copy()

    # Build the full DataFrame for the pipeline: replace the tail of the
    # full dataset with our modified context (so spatial sees neighbors).
    full_mod = full_df.copy()
    full_mod = full_mod.drop(
        index=full_mod[
            (full_mod["station_id"] == station_id)
            & (full_mod["timestamp"].isin(context["timestamp"]))
        ].index
    )
    full_mod = pd.concat([full_mod, context], ignore_index=True)
    full_mod = full_mod.sort_values("timestamp").reset_index(drop=True)

    # Run the frozen pipeline
    feats = build_features(full_mod)
    qc = apply_qc_rules(feats)

    # Spatial: use the metadata
    meta = pd.read_csv(META_CSV) if os.path.exists(META_CSV) else None
    if meta is not None:
        # Suppress the neighbour graph print by capturing stdout
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            spatial = apply_spatial_analysis(full_mod, meta)
    else:
        spatial = full_mod[["station_id", "timestamp"]].copy()
        spatial["spatial_isolated_flag"] = 0
        spatial["spatial_common_event_flag"] = 0
        spatial["spatial_any_flag"] = 0
        spatial["spatial_neighbours_n"] = 0

    temporal = apply_temporal_detector(full_mod)

    # Keep only the columns we need
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    sp_cols = ["station_id", "timestamp"] + [
        c for c in spatial.columns if c.startswith("spatial_")
    ]
    tp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]

    joined = full_mod.merge(qc[qc_cols], on=["station_id", "timestamp"], how="left")
    joined = joined.merge(spatial[sp_cols], on=["station_id", "timestamp"], how="left")
    joined = joined.merge(temporal[tp_cols], on=["station_id", "timestamp"], how="left")

    # Add delta columns
    delta_cols = ["station_id", "timestamp", "d_temperature", "d_pressure", "d_humidity"]
    delta_cols = [c for c in delta_cols if c in feats.columns]
    joined = joined.merge(feats[delta_cols], on=["station_id", "timestamp"], how="left")

    classified = classify_anomalies(joined)
    scored = score_anomalies(classified)
    fused = fuse_evidence(scored)

    # Find our injected row
    target_ts = context.loc[last_idx, "timestamp"]
    injected = fused[
        (fused["station_id"] == station_id) & (fused["timestamp"] == target_ts)
    ]
    if injected.empty:
        raise RuntimeError(f"Could not find injected row in pipeline output")

    row = injected.iloc[0]

    # Build the alert using the SAME reasoning functions as production
    class RowWrapper:
        def __init__(self, d):
            self._d = d
        def get(self, key, default=None):
            try:
                return self._d.get(key, default)
            except AttributeError:
                return self._d[key] if key in self._d else default
        def __contains__(self, key):
            return key in self._d
        @property
        def index(self):
            return list(self._d.keys())

    wrapped = RowWrapper(row.to_dict())

    multivariate = _compute_multivariate_analysis(wrapped)
    evidence = _compute_evidence_breakdown(wrapped)
    counter = _compute_counter_reasoning(wrapped)
    weather_verdict = _compute_genuine_weather_verdict(wrapped, multivariate)
    physical = _compute_physical_reasoning(wrapped)
    trust = _compute_trust_score(wrapped, evidence["evidence_breakdown"])
    event_class = _compute_event_class(wrapped)

    severity = row.get("severity", "High")
    confidence = int(row.get("anomaly_confidence", 0) or 0)
    priority = _compute_priority(
        severity=severity,
        confidence=confidence,
        spatial_isolated=bool(int(row.get("spatial_isolated_flag", 0) or 0)),
    )

    alert = {
        "station_id": row.get("station_id"),
        "timestamp": str(row.get("timestamp")),
        "temperature": float(row.get("temperature")) if pd.notna(row.get("temperature")) else None,
        "pressure": float(row.get("pressure")) if pd.notna(row.get("pressure")) else None,
        "humidity": float(row.get("humidity")) if pd.notna(row.get("humidity")) else None,
        "status": "anomaly",
        "anomaly_type": row.get("anomaly_class", "Unclassified"),
        "confidence": confidence,
        "severity": severity,
        "priority": priority,
        "trust_score": trust,
        "physical_reasoning": physical,
        "weather_verdict_reason": weather_verdict.get("weather_verdict_reason", ""),
        "maintenance_recommendation": "Inspect the affected station/sensor.",
        "corrected_temperature": None,
        "corrected_pressure": None,
        "corrected_humidity": None,
        "decision_basis": evidence["decision_basis"],
        "counter_evidence": evidence["counter_evidence"],
        "counter_reasoning": counter,
        "multivariate_analysis": multivariate,
        "defensibility": _compute_defensibility(wrapped, evidence, multivariate, weather_verdict),
        "evidence_breakdown": evidence["evidence_breakdown"],
        "genuine_weather_event": weather_verdict.get("genuine_weather_event", False),
        "event_class": event_class,
        "_demo": True,
        "_injected_fault": fault_type,
        "_injected_magnitude": magnitude,
    }

    return {
        "station_id": station_id,
        "fault_type": fault_type,
        "magnitude": magnitude,
        "original_reading": {
            "temperature": float(original_row["temperature"]),
            "pressure": float(original_row["pressure"]),
            "humidity": float(original_row["humidity"]),
        },
        "modified_reading": {
            "temperature": float(modified_row["temperature"]),
            "pressure": float(modified_row["pressure"]),
            "humidity": float(modified_row["humidity"]),
        },
        "alert": alert,
    }


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def inject_and_detect(
    station_id: str,
    fault_type: str,
    magnitude: Optional[float] = None,
) -> dict:
    if fault_type not in FAULT_TYPES:
        raise ValueError(f"Unknown fault_type: {fault_type}")
    if magnitude is None:
        magnitude = DEFAULT_MAGNITUDE.get(fault_type, 5.0)
    return _run_pipeline_on_injection(station_id, fault_type, magnitude)


if __name__ == "__main__":
    import json
    result = inject_and_detect("AWS_01", "temperature_spike", 15.0)
    print(json.dumps(result, indent=2, default=str))