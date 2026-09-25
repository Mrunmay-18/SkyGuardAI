"""
src/sensor_health.py
SkyGuard AI - STEP 20: Sensor Health (Historical Maintenance Risk).

Estimates the HISTORICAL maintenance risk of each AWS station using
observed detector behavior from the existing SkyGuard AI pipeline.

This is NOT a sensor-failure prediction model. It does NOT claim that
a sensor will definitely fail, or predict a specific future failure
time. It only summarizes OBSERVED HISTORICAL behavior and estimates
maintenance risk.

The purpose of this module is to demonstrate a TRANSPARENT
ARCHITECTURE for aggregating historical detector evidence into a
station-level maintenance risk indicator. The specific thresholds
and weights are PROTOTYPE OPERATIONAL HEURISTICS, not scientifically
validated maintenance standards, and must not be interpreted as
official guidance.

All weights and normalization thresholds are PROTOTYPE OPERATIONAL
HEURISTICS for demonstration and prioritization. They are NOT
scientifically validated maintenance standards and must NOT be tuned
on ground-truth anomaly labels. The specific numeric thresholds are
illustrative and are expected to be replaced by domain-calibrated
values in a production deployment.

Does NOT modify any existing file.    anomaly_count (and the displayed "Repeated anomaly evidence")
    is the UNION of rows where any of the four evidence sources
    fired:
        predicted_anomaly OR qc_any_flag
        OR temporal_predicted_anomaly OR spatial_isolated_flag
    It counts ROWS with evidence, not confirmed sensor faults.
    A single row with multiple flags still counts as 1.
"""

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
@dataclass
class SensorHealthConfig:
    """
    Configuration for sensor health scoring.

    All weights and normalization thresholds are PROTOTYPE OPERATIONAL
    HEURISTICS for demonstration and prioritization. They are NOT
    scientifically validated maintenance standards and must NOT be
    tuned on ground-truth anomaly labels.

    The purpose of this module is to demonstrate a TRANSPARENT
    ARCHITECTURE for aggregating historical detector evidence into
    a station-level maintenance risk indicator. The specific numeric
    thresholds are illustrative and are expected to be replaced by
    domain-calibrated values in a production deployment.
    """

    # Component weights (must sum to 1.0).
    W_ANOMALY_RATE: float = 0.35
    W_DRIFT: float = 0.20
    W_GAP_FLAG: float = 0.15
    W_FROZEN: float = 0.20
    W_FAILURE: float = 0.10

    # Normalization thresholds — each component is normalized to
    # [0, 1] by dividing the observed RATE by these.
    # PROTOTYPE OPERATIONAL HEURISTICS, not validated standards.
    NORM_ANOMALY_RATE: float = 0.20    # 20% anomaly rate → 1.0
    NORM_DRIFT_RATE: float = 0.02      # 2% drift rate → 1.0
    NORM_GAP_FLAG_RATE: float = 0.01   # 1% gap-flag rate → 1.0
    NORM_FROZEN_RATE: float = 0.05     # 5% frozen rate → 1.0
    NORM_FAILURE_RATE: float = 0.005   # 0.5% failure rate → 1.0

    # Status thresholds (prototype heuristic tiers).
    STATUS_HEALTHY_MAX: int = 29       # 0..29 → Healthy
    STATUS_WATCH_MAX: int = 59         # 30..59 → Watch
    # 60..100 → At Risk


# ----------------------------------------------------------------------
# Safe column access
# ----------------------------------------------------------------------
def _safe_int_arr(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Return column as int array; missing or NaN → 0."""
    if col in df.columns:
        return df[col].fillna(0).astype(int).to_numpy()
    return np.zeros(n, dtype=int)


def _safe_str_arr(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Return column as str array; missing → ''."""
    if col in df.columns:
        return df[col].fillna("").astype(str).to_numpy()
    return np.array([""] * n, dtype=object)


# ----------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------
def calculate_sensor_health(
    df: pd.DataFrame,
    config: SensorHealthConfig | None = None,
) -> pd.DataFrame:
    """
    Calculate station-level historical maintenance risk from observed
    detector evidence.

    Aggregates per-station signals (anomaly rate, drift count, gap
    flags, frozen readings, failure evidence) into a transparent
    weighted maintenance risk indicator (0..100) and a status category.

    Parameters
    ----------
    df : pd.DataFrame
        Joined observations with evidence-source outputs. Missing
        columns are tolerated — treated as 0 evidence.
    config : SensorHealthConfig | None
        Optional configuration. Defaults to SensorHealthConfig().

    Returns
    -------
    pd.DataFrame
        Station-level summary with EXACTLY ONE ROW PER station_id.
        Sorted by maintenance_risk_indicator descending, then
        station_id ascending. Columns:
          station_id, valid_observations, anomaly_count,
          anomaly_rate, drift_count,
          supporting_temporal_drift_count, missing_count,
          frozen_count, failure_count,
          maintenance_risk_indicator, maintenance_status,
          maintenance_health_reason.

    Ground-truth columns (is_anomaly, anomaly_type,
    injected_parameter) are NOT used for scoring. No future
    information is used.
        anomaly_count (and the displayed "Repeated anomaly evidence")
    is the UNION of rows where any of the four evidence sources
    fired:
        predicted_anomaly OR qc_any_flag
        OR temporal_predicted_anomaly OR spatial_isolated_flag
    It counts ROWS with evidence, not confirmed sensor faults.
    A single row with multiple flags still counts as 1."""
    if config is None:
        config = SensorHealthConfig()

    # Work on a copy; do NOT mutate input.
    out = df.copy()
    n = len(out)

    # Drop rows with NaN station_id or timestamp for valid_observations.
    if "station_id" in out.columns:
        out = out[out["station_id"].notna()].copy()

    # Extract evidence flags (safe, missing → 0).
    predicted_anomaly = _safe_int_arr(out, "predicted_anomaly", len(out))
    qc_any = _safe_int_arr(out, "qc_any_flag", len(out))
    temporal_pred = _safe_int_arr(out, "temporal_predicted_anomaly", len(out))
    spatial_iso = _safe_int_arr(out, "spatial_isolated_flag", len(out))
    qc_gap = _safe_int_arr(out, "qc_gap_flag", len(out))
    qc_persistence = _safe_int_arr(out, "qc_persistence_flag", len(out))
    temporal_l2 = _safe_int_arr(out, "temporal_level2_flag", len(out))
    anomaly_class = _safe_str_arr(out, "anomaly_class", len(out))

    # Compute the "any fault evidence" union per row.
    any_evidence = (
        (predicted_anomaly == 1)
        | (qc_any == 1)
        | (temporal_pred == 1)
        | (spatial_iso == 1)
    ).astype(int)

    # Drift classification: ONLY anomaly_class == "Calibration Drift".
    # Do NOT include temporal_level2_flag in drift_count.
    is_drift = (anomaly_class == "Calibration Drift").astype(int)

    # Frozen: qc_persistence_flag == 1 OR anomaly_class == "Frozen Sensor".
    is_frozen = (
        (qc_persistence == 1) | (anomaly_class == "Frozen Sensor")
    ).astype(int)

    # Failure: anomaly_class == "Communication Failure".
    is_failure = (anomaly_class == "Communication Failure").astype(int)

    # Gap flags: qc_gap_flag == 1 (annotates the row PRECEDING a gap,
    # not the missing row itself — this is a gap-flag count, not a
    # true missing-observation count).
    is_gap_flag = qc_gap

    # Supporting temporal drift (separate, NEVER added to drift_count).
    is_supporting_drift = temporal_l2

    # Put computed per-row arrays back into the DataFrame for groupby.
    out["_any_evidence"] = any_evidence
    out["_is_drift"] = is_drift
    out["_is_frozen"] = is_frozen
    out["_is_failure"] = is_failure
    out["_is_gap_flag"] = is_gap_flag
    out["_is_supporting_drift"] = is_supporting_drift

    # Aggregate per station.
    rows = []
    for sid, g in out.groupby("station_id"):
        valid_obs = len(g)
        anomaly_count = int(g["_any_evidence"].sum())
        anomaly_rate = anomaly_count / valid_obs if valid_obs > 0 else 0.0
        drift_count = int(g["_is_drift"].sum())
        supporting_drift = int(g["_is_supporting_drift"].sum())
        missing_count = int(g["_is_gap_flag"].sum())
        frozen_count = int(g["_is_frozen"].sum())
        failure_count = int(g["_is_failure"].sum())

        # Normalized rates (clamped to [0, 1]).
        norm_anomaly = min(
            1.0, anomaly_rate / config.NORM_ANOMALY_RATE
        ) if config.NORM_ANOMALY_RATE > 0 else 0.0
        drift_rate = drift_count / valid_obs if valid_obs > 0 else 0.0
        norm_drift = min(
            1.0, drift_rate / config.NORM_DRIFT_RATE
        ) if config.NORM_DRIFT_RATE > 0 else 0.0
        gap_rate = missing_count / valid_obs if valid_obs > 0 else 0.0
        norm_gap = min(
            1.0, gap_rate / config.NORM_GAP_FLAG_RATE
        ) if config.NORM_GAP_FLAG_RATE > 0 else 0.0
        frozen_rate = frozen_count / valid_obs if valid_obs > 0 else 0.0
        norm_frozen = min(
            1.0, frozen_rate / config.NORM_FROZEN_RATE
        ) if config.NORM_FROZEN_RATE > 0 else 0.0
        failure_rate = failure_count / valid_obs if valid_obs > 0 else 0.0
        norm_failure = min(
            1.0, failure_rate / config.NORM_FAILURE_RATE
        ) if config.NORM_FAILURE_RATE > 0 else 0.0

        # Weighted sum.
        raw = (
            config.W_ANOMALY_RATE * norm_anomaly
            + config.W_DRIFT * norm_drift
            + config.W_GAP_FLAG * norm_gap
            + config.W_FROZEN * norm_frozen
            + config.W_FAILURE * norm_failure
        )
        risk = int(np.clip(round(100 * raw), 0, 100))

        # Status.
        if risk <= config.STATUS_HEALTHY_MAX:
            status = "Healthy"
        elif risk <= config.STATUS_WATCH_MAX:
            status = "Watch"
        else:
            status = "At Risk"

        # Maintenance health reason.
        reason = _build_reason(
            status, anomaly_count, anomaly_rate,
            drift_count, frozen_count, missing_count,
            failure_count,
        )

        rows.append({
            "station_id": sid,
            "valid_observations": valid_obs,
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_rate,
            "drift_count": drift_count,
            "supporting_temporal_drift_count": supporting_drift,
            "missing_count": missing_count,
            "frozen_count": frozen_count,
            "failure_count": failure_count,
            "maintenance_risk_indicator": risk,
            "maintenance_status": status,
            "maintenance_health_reason": reason,
        })

    result = pd.DataFrame(rows)

    # Sort by risk descending, then station_id ascending.
    result = result.sort_values(
        ["maintenance_risk_indicator", "station_id"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return result


# ----------------------------------------------------------------------
# Reason builder
# ----------------------------------------------------------------------
def _build_reason(
    status: str,
    anomaly_count: int,
    anomaly_rate: float,
    drift_count: int,
    frozen_count: int,
    gap_count: int,
    failure_count: int,
) -> str:
    """
    Build a concise maintenance_health_reason per station.

    Reflects ONLY evidence that actually exists. Mentions specific
    components with count > 0 in priority order (highest weight first).
    Never claims evidence that isn't present.
    """
    if status == "Healthy":
        return (
            "No significant repeated anomaly, drift, gap-flag, "
            "frozen-reading, or failure evidence was observed."
        )

    # Build a list of components with count > 0, in weight-priority order.
    parts = []
    if anomaly_count > 0:
        parts.append(
            f"repeated anomaly evidence ({anomaly_count} observations, "
            f"{anomaly_rate:.1%})"
        )
    if drift_count > 0:
        parts.append(f"drift evidence ({drift_count})")
    if frozen_count > 0:
        parts.append(f"frozen readings ({frozen_count})")
    if gap_count > 0:
        parts.append(f"gap flags ({gap_count})")
    if failure_count > 0:
        parts.append(f"failure evidence ({failure_count})")

    if parts:
        sentence = ", ".join(parts)
        return sentence[0].upper() + sentence[1:] + "."
    else:
        return (
            "Elevated maintenance risk indicator computed, but "
            "no individual evidence component dominates."
        )


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402
    from qc_rules import apply_qc_rules  # noqa: E402
    from spatial_analysis import apply_spatial_analysis  # noqa: E402
    from temporal_detector import apply_temporal_detector  # noqa: E402
    from anomaly_classifier import classify_anomalies  # noqa: E402
    from scoring import score_anomalies  # noqa: E402

    print("=" * 60)
    print("SkyGuard AI - Sensor Health Demo")
    print("=" * 60)

    # 1. Load test data.
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])

    # 2-3. Build features + QC.
    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()

    # 4. Spatial analysis (suppress neighbour graph print).
    metadata = pd.read_csv("data/station_metadata.csv")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spatial = apply_spatial_analysis(obs, metadata)
    spatial_cols = ["station_id", "timestamp"] + [
        c for c in spatial.columns if c.startswith("spatial_")
    ]
    spatial = spatial[spatial_cols].copy()

    # 5. Temporal detector.
    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()

    # 6. Load IF predictions.
    if_df = pd.read_csv("data/isolation_forest_predictions.csv")
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()

    # 7. Merge all evidence.
    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(spatial, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(temporal, on=["station_id", "timestamp"], how="left")

    # 8. Classify.
    classified = classify_anomalies(joined)

    # 9. Score.
    scored = score_anomalies(classified)

    # 10. Calculate sensor health.
    health = calculate_sensor_health(scored)

    # Print results.
    print(f"\nTotal stations: {len(health)}\n")

    for _, row in health.iterrows():
        print(f"Station: {row['station_id']}")
        print(f"  Valid observations:         {row['valid_observations']}")
        print(f"  Repeated anomaly evidence:  {row['anomaly_count']} "
              f"({row['anomaly_rate']:.1%})")
        print(f"  Drift evidence:             {row['drift_count']}")
        print(f"  Supporting temporal drift:  {row['supporting_temporal_drift_count']}")
        print(f"  Gap flags:                  {row['missing_count']}")
        print(f"  Frozen readings:            {row['frozen_count']}")
        print(f"  Failure evidence:           {row['failure_count']}")
        print(f"\n  Maintenance Risk Indicator: "
              f"{row['maintenance_risk_indicator']}/100")
        print(f"  Status: {row['maintenance_status']}")
        print(f"\n  Reason:")
        print(f"    {row['maintenance_health_reason']}")
        print()

    # Summary.
    n_healthy = int((health["maintenance_status"] == "Healthy").sum())
    n_watch = int((health["maintenance_status"] == "Watch").sum())
    n_risk = int((health["maintenance_status"] == "At Risk").sum())
    print("-" * 60)
    print("Summary:")
    print(f"  Healthy:  {n_healthy}")
    print(f"  Watch:    {n_watch}")
    print(f"  At Risk:  {n_risk}")
    print()
    print(
        "Note: these status categories are prototype operational "
        "heuristics, not official maintenance standards. The "
        "purpose of this module is to demonstrate a transparent "
        "aggregation architecture, not to validate specific "
        "thresholds against the injected test anomalies."
    )