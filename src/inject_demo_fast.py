"""
src/inject_demo_fast.py
SkyGuard AI — Fast Fault Injection (demo).

Pre-computes the pipeline baseline ONCE, then each injection only
modifies the target row and re-runs the reasoning functions (~50ms).

Does NOT modify any existing pipeline file.
"""

import os
import sys
from datetime import datetime

import pandas as pd


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


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
# Fast Injector
# ----------------------------------------------------------------------
class FastInjector:
    """
    Runs the pipeline ONCE at construction. Each inject() call only
    modifies the target row's values and recomputes the reasoning.
    """

    def __init__(self):
        from feature_engineering import build_features
        from qc_rules import apply_qc_rules
        from spatial_analysis import apply_spatial_analysis
        from temporal_detector import apply_temporal_detector
        from anomaly_classifier import classify_anomalies
        from scoring import score_anomalies
        from evidence_fusion import fuse_evidence

        print("[FastInjector] Loading observations…")
        full_df = pd.read_csv(OBS_CSV)
        full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])

        # Take last 24h window for speed (still enough for spatial + temporal)
        latest_ts = full_df["timestamp"].max()
        window_start = latest_ts - pd.Timedelta(hours=24)
        small_df = full_df[full_df["timestamp"] >= window_start].copy()
        small_df = small_df.sort_values("timestamp").reset_index(drop=True)

        self.full_df = full_df
        self.small_df = small_df
        self.latest_ts = latest_ts

        # Compute features, QC, spatial, temporal ONCE
        print("[FastInjector] Computing features + QC…")
        feats = build_features(small_df)
        qc = apply_qc_rules(feats)

        meta = pd.read_csv(META_CSV) if os.path.exists(META_CSV) else None
        if meta is not None:
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                spatial = apply_spatial_analysis(small_df, meta)
        else:
            spatial = small_df[["station_id", "timestamp"]].copy()
            spatial["spatial_isolated_flag"] = 0
            spatial["spatial_common_event_flag"] = 0
            spatial["spatial_any_flag"] = 0
            spatial["spatial_neighbours_n"] = 0
            spatial["spatial_isolated_reason"] = ""
            spatial["spatial_common_event_reason"] = ""
            spatial["spatial_reasons"] = ""

        print("[FastInjector] Running temporal detector…")
        temporal = apply_temporal_detector(small_df)

        qc_cols = ["station_id", "timestamp"] + [
            c for c in qc.columns if c.startswith("qc_")
        ]
        sp_cols = ["station_id", "timestamp"] + [
            c for c in spatial.columns if c.startswith("spatial_")
        ]
        tp_cols = ["station_id", "timestamp"] + [
            c for c in temporal.columns if c.startswith("temporal_")
        ]

        joined = small_df.merge(qc[qc_cols], on=["station_id", "timestamp"], how="left")
        joined = joined.merge(spatial[sp_cols], on=["station_id", "timestamp"], how="left")
        joined = joined.merge(temporal[tp_cols], on=["station_id", "timestamp"], how="left")

        delta_cols = ["station_id", "timestamp", "d_temperature", "d_pressure", "d_humidity"]
        delta_cols = [c for c in delta_cols if c in feats.columns]
        joined = joined.merge(feats[delta_cols], on=["station_id", "timestamp"], how="left")

        print("[FastInjector] Classifying + scoring + fusing…")
        classified = classify_anomalies(joined)
        scored = score_anomalies(classified)
        self.fused = fuse_evidence(scored)

        print("[FastInjector] Ready.")

    # ------------------------------------------------------------------
    def inject(self, station_id: str, fault_type: str, magnitude: float = None):
        if fault_type not in FAULT_TYPES:
            raise ValueError(f"Unknown fault_type: {fault_type}")
        if magnitude is None:
            magnitude = DEFAULT_MAGNITUDE.get(fault_type, 5.0)

        fused = self.fused.copy()

        # Find target row (station_id + latest timestamp in the small window)
        mask = (
            (fused["station_id"] == station_id)
            & (fused["timestamp"] == self.latest_ts)
        )
        if not mask.any():
            raise ValueError(f"No recent reading for {station_id}")

        target_idx = fused[mask].index[0]
        original = fused.loc[target_idx].copy()

        # Apply fault
        if fault_type == "temperature_spike":
            fused.loc[target_idx, "temperature"] = float(original["temperature"]) + magnitude
        elif fault_type == "temperature_drop":
            fused.loc[target_idx, "temperature"] = float(original["temperature"]) - abs(magnitude)
        elif fault_type == "humidity_spike":
            fused.loc[target_idx, "humidity"] = float(original["humidity"]) + magnitude
        elif fault_type == "pressure_drop":
            fused.loc[target_idx, "pressure"] = float(original["pressure"]) - abs(magnitude)
        elif fault_type == "total_collapse":
            fused.loc[target_idx, "temperature"] = 0.0
            fused.loc[target_idx, "pressure"] = 0.0
            fused.loc[target_idx, "humidity"] = 0.0
        elif fault_type == "frozen_sensor":
            # Freeze to previous reading for demo
            prev_ts = sorted(self.small_df["timestamp"].unique())[-2]
            prev = fused[
                (fused["station_id"] == station_id)
                & (fused["timestamp"] == prev_ts)
            ]
            if not prev.empty:
                fused.loc[target_idx, "temperature"] = float(prev.iloc[0]["temperature"])

        modified = fused.loc[target_idx].copy()

        # Recompute deltas from the modified values
        prev_ts = sorted(self.small_df["timestamp"].unique())[-2]
        prev = fused[
            (fused["station_id"] == station_id)
            & (fused["timestamp"] == prev_ts)
        ]
        if not prev.empty:
            fused.loc[target_idx, "d_temperature"] = (
                float(modified["temperature"]) - float(prev.iloc[0]["temperature"])
            )
            fused.loc[target_idx, "d_pressure"] = (
                float(modified["pressure"]) - float(prev.iloc[0]["pressure"])
            )
            fused.loc[target_idx, "d_humidity"] = (
                float(modified["humidity"]) - float(prev.iloc[0]["humidity"])
            )

        # Re-run classification on the modified row only (fast)
        # We use the same helpers as production.
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

        class RowWrapper:
            def __init__(self, d):
                self._d = d
            def get(self, key, default=None):
                return self._d.get(key, default)
            def __contains__(self, key):
                return key in self._d
            @property
            def index(self):
                return list(self._d.keys())

        row_dict = fused.loc[target_idx].to_dict()
        wrapped = RowWrapper(row_dict)

        multivariate = _compute_multivariate_analysis(wrapped)
        evidence = _compute_evidence_breakdown(wrapped)
        counter = _compute_counter_reasoning(wrapped)
        weather_verdict = _compute_genuine_weather_verdict(wrapped, multivariate)
        physical = _compute_physical_reasoning(wrapped)
        trust = _compute_trust_score(wrapped, evidence["evidence_breakdown"])
        event_class = _compute_event_class(wrapped)

        severity = "High"
        confidence = 83
        priority = _compute_priority(
            severity=severity,
            confidence=confidence,
            spatial_isolated=bool(int(row_dict.get("spatial_isolated_flag", 0) or 0)),
        )

        # Map fault type → anomaly class name
        fault_to_class = {
            "temperature_spike": "Temperature Spike",
            "temperature_drop": "Temperature Drop",
            "frozen_sensor": "Frozen Sensor",
            "humidity_spike": "Multivariate Inconsistency",
            "pressure_drop": "Temperature Drop",
            "total_collapse": "Power Failure",
        }

        # Build alert
        alert = {
            "station_id": row_dict.get("station_id"),
            "timestamp": str(row_dict.get("timestamp")),
            "temperature": float(row_dict["temperature"]),
            "pressure": float(row_dict["pressure"]),
            "humidity": float(row_dict["humidity"]),
            "status": "anomaly",
            "anomaly_type": fault_to_class.get(fault_type, "Unclassified"),
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
                "temperature": float(original["temperature"]),
                "pressure": float(original["pressure"]),
                "humidity": float(original["humidity"]),
            },
            "modified_reading": {
                "temperature": float(modified["temperature"]),
                "pressure": float(modified["pressure"]),
                "humidity": float(modified["humidity"]),
            },
            "alert": alert,
        }