"""
src/scoring.py
SkyGuard AI - STEP 18: Confidence + Severity Scoring Layer.

TRANSPARENT, RULE-BASED scoring layer producing TWO INDEPENDENT
outputs per row:
    anomaly_confidence  — integer 0..100 (evidence strength)
    severity            — "Low" | "Medium" | "High" | "Critical"
                          (operational importance)

These are DIFFERENT quantities:
    - Confidence = "how strong is our evidence that this row is
                    anomalous?"
    - Severity   = "if this is a real fault, how operationally
                    important is it?"

The module refers to 4 EVIDENCE SOURCES (not "4 detectors"):
    1. "Isolation Forest"    — the ML detector
    2. "QC rules"            — the rule-based quality-control engine
    3. "Spatial consistency" — the cross-station evidence system
    4. "Temporal detector"   — the sequence-level evidence system

Only the Isolation Forest is a single trained model; the others are
rule-based evidence systems.

SEVERITY THRESHOLDS ARE PROTOTYPE OPERATIONAL HEURISTICS for
demonstration and prioritization. They are NOT official
meteorological, disaster-management, or safety severity standards.

CONFIDENCE IS NOT A PROBABILITY. It is a rule-based evidence-strength
integer on [0, 100]. It is not calibrated against any frequency-based
model, does not use a % symbol, and must never be described as a
probability in code, comments, docstrings, or output strings.

Does NOT modify any existing file. Uses pandas and numpy only.
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
class ScoringConfig:
    """
    Configuration for the scoring layer.

    All weights and thresholds are PROTOTYPE HEURISTICS for
    demonstration and prioritization. They are NOT official
    meteorological, disaster-management, or safety severity
    standards.
    """

    # ---- Confidence weights (must sum to 1.0) ----
    # These are PROTOTYPE HEURISTICS, not calibrated values.
    W_COUNT: float = 0.5        # Dimension 1: how many sources fired
    W_AGREEMENT: float = 0.3    # Dimension 2: do sources agree
    W_CATEGORICAL: float = 0.2  # Dimension 3: classifier confidence

    # ---- Confidence special-case cap ----
    # Spatial isolation alone is supporting evidence, not proof.
    SPATIAL_ONLY_CAP: int = 40

    # ---- Severity thresholds (PROTOTYPE OPERATIONAL HEURISTICS) ----
    # These are NOT official meteorological or safety standards.
    SEVERITY_MAGNITUDE_MODERATE: float = 3.0   # |z| >= 3.0 → moderate
    SEVERITY_MAGNITUDE_STRONG: float = 5.0    # |z| > 5.0 → strong

    # ---- Confidence label format ----
    # MUST be "Anomaly Confidence: <N>/100" — no %, no decimal, no "probability".
    CONFIDENCE_LABEL_FORMAT: str = "Anomaly Confidence: {n}/100"


# ----------------------------------------------------------------------
# Safe column access
# ----------------------------------------------------------------------
def _safe_int_arr(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Return column as int array; missing or NaN → 0."""
    if col in df.columns:
        return df[col].fillna(0).astype(int).to_numpy()
    return np.zeros(n, dtype=int)


def _safe_float_arr(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Return column as float array; missing → NaN."""
    if col in df.columns:
        return df[col].to_numpy(dtype=float)
    return np.full(n, np.nan)


def _safe_str_arr(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Return column as str array; missing → ''."""
    if col in df.columns:
        return df[col].fillna("").astype(str).to_numpy()
    return np.array([""] * n, dtype=object)


# ----------------------------------------------------------------------
# Confidence computation
# ----------------------------------------------------------------------
def _compute_confidence(
    if_flag: np.ndarray,
    qc_any: np.ndarray,
    spatial_iso: np.ndarray,
    temporal_pred: np.ndarray,
    categorical_conf: np.ndarray,
    config: ScoringConfig,
) -> tuple:
    """
    Compute anomaly_confidence (0..100) from three dimensions.

    Dimension 1 — Evidence count: how many of the 4 evidence sources
    fired on this row.
    Dimension 2 — Agreement: do sources agree, or is only one firing?
    Dimension 3 — Categorical confidence: the classifier's own
    confidence for this row.

    Returns (confidence_int_array, confidence_label_array).
    """
    n = len(if_flag)

    # Evidence count: how many of the 4 sources fired.
    evidence_count = if_flag + qc_any + spatial_iso + temporal_pred
    evidence_count_norm = evidence_count / 4.0

    # Agreement: a lookup table based on how many sources fired.
    # 0 → 0.0, 1 → 0.3, 2 → 0.6, 3 → 0.85, 4 → 1.0
    agreement_lookup = np.array([0.0, 0.3, 0.6, 0.85, 1.0])
    agreement = agreement_lookup[np.clip(evidence_count, 0, 4)]

    # Categorical confidence: map the classifier's confidence labels.
    # "high" → 1.0, "medium" → 0.6, "low" → 0.3, absent/other → 0.5
    cat_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    categorical_val = np.full(n, 0.5)  # neutral default for absent
    for i in range(n):
        label = str(categorical_conf[i]).strip().lower()
        if label in cat_map:
            categorical_val[i] = cat_map[label]

    # Raw confidence (weighted sum of 3 dimensions).
    raw = (
        config.W_COUNT * evidence_count_norm
        + config.W_AGREEMENT * agreement
        + config.W_CATEGORICAL * categorical_val
    )

    confidence = np.clip((100 * raw).round().astype(int), 0, 100)

    # Special case: if evidence_count == 0 → confidence = 0.
    confidence[evidence_count == 0] = 0

    # Special case: if evidence_count == 1 and that source is spatial
    # isolation only → cap at SPATIAL_ONLY_CAP.
    spatial_only_mask = (
        (evidence_count == 1)
        & (spatial_iso == 1)
        & (if_flag == 0)
        & (qc_any == 0)
        & (temporal_pred == 0)
    )
    confidence[spatial_only_mask] = np.minimum(
        confidence[spatial_only_mask], config.SPATIAL_ONLY_CAP
    )

    # Build labels: "Anomaly Confidence: <N>/100"
    labels = np.array([
        config.CONFIDENCE_LABEL_FORMAT.format(n=int(c))
        for c in confidence
    ], dtype=object)

    return confidence, labels


# ----------------------------------------------------------------------
# Severity computation
# ----------------------------------------------------------------------
def _compute_severity(
    temporal_z4: np.ndarray,
    temporal_z8: np.ndarray,
    temporal_z16: np.ndarray,
    temporal_l2: np.ndarray,
    qc_persistence: np.ndarray,
    qc_temporal: np.ndarray,
    qc_range: np.ndarray,
    qc_internal: np.ndarray,
    spatial_iso: np.ndarray,
    spatial_com: np.ndarray,
    if_flag: np.ndarray,
    qc_any: np.ndarray,
    temporal_pred: np.ndarray,
    config: ScoringConfig,
) -> tuple:
    """
    Compute severity tier from four factors.

    Factor 1 — Magnitude: max |temporal_z_*| (NaN-safe).
    Factor 2 — Persistence: sustained / brief / none.
    Factor 3 — Multi-parameter evidence: count of active QC categories.
    Factor 4 — Spatial extent: regional / isolated / unknown.

    All thresholds are PROTOTYPE OPERATIONAL HEURISTICS.

    Returns (severity_array, severity_reason_array).
    """
    n = len(if_flag)

    # Factor 1: Magnitude (max |z| across 3 windows, NaN-safe).
    # Replace NaN with -inf so np.max ignores them; if all three are
    # NaN for a row the result is -inf, which we convert to 0.0.
    # This avoids the RuntimeWarning from np.nanmax on all-NaN slices.
    z_stack = np.stack([temporal_z4, temporal_z8, temporal_z16])
    abs_z = np.abs(z_stack)
    abs_z_safe = np.where(np.isnan(abs_z), -np.inf, abs_z)
    max_z = np.max(abs_z_safe, axis=0)
    max_z = np.where(np.isneginf(max_z), 0.0, max_z)

    magnitude_str = np.where(
        max_z > config.SEVERITY_MAGNITUDE_STRONG, "strong",
        np.where(max_z >= config.SEVERITY_MAGNITUDE_MODERATE, "moderate", "weak"),
    )

    # Factor 2: Persistence.
    persistence = np.where(
        (temporal_l2 == 1) | (qc_persistence == 1), "sustained",
        np.where(qc_temporal == 1, "brief", "none"),
    )

    # Factor 3: Multi-parameter evidence (count of active QC categories).
    # This is a PROXY for how many independent measurement dimensions
    # show anomalies — the QC schema returns category-level flags, not
    # parameter-level flags. Call this "multi-parameter evidence", NOT
    # "parameters affected".
    multi_count = qc_range + qc_internal + qc_temporal + qc_persistence
    multi_str = np.where(multi_count >= 2, "multiple", "single")

    # Factor 4: Spatial extent.
    spatial_ext = np.where(
        spatial_com == 1, "regional",
        np.where(spatial_iso == 1, "isolated", "unknown"),
    )

    # Evidence count (for the "no evidence → Low" rule).
    evidence_count = if_flag + qc_any + spatial_iso + temporal_pred

    # Severity tier assignment (deterministic, priority-ordered).
    # Each tier's rule contains only necessary terms.
    severity = np.array([""] * n, dtype=object)
    reasons = np.array([""] * n, dtype=object)

    for i in range(n):
        mag = magnitude_str[i]
        pers = persistence[i]
        multi = multi_str[i]
        spat = spatial_ext[i]
        mz = max_z[i]
        mc = int(multi_count[i])

        # Build reason string.
        reason_parts = [
            f"magnitude={mag} (max z={mz:.1f})",
            f"persistence={pers}",
            f"multi-parameter evidence={mc} categories",
            f"spatial={spat}",
        ]

        # Tier assignment.
        if evidence_count[i] == 0:
            tier = "Low"
        elif mag == "strong" and pers == "sustained":
            tier = "Critical"
        elif (
            mag == "strong"
            or (mag == "moderate" and pers == "sustained")
            or (mag == "moderate" and multi == "multiple")
        ):
            tier = "High"
        elif (
            mag == "moderate"
            or pers == "sustained"
            or multi == "multiple"
        ):
            tier = "Medium"
        else:
            tier = "Low"

        severity[i] = tier
        reasons[i] = "; ".join(reason_parts)

    return severity, reasons


# ----------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------
def score_anomalies(
    df: pd.DataFrame,
    config: ScoringConfig | None = None,
) -> pd.DataFrame:
    """
    Add confidence and severity columns to a DataFrame of observations
    with detector outputs.

    Parameters
    ----------
    df : pd.DataFrame
        Joined observations with evidence-source outputs. Missing
        columns are tolerated — treated as absent evidence.
    config : ScoringConfig | None
        Optional configuration. Defaults to ScoringConfig().

    Returns
    -------
    pd.DataFrame
        Copy of df with ADDED columns:
          anomaly_confidence         (int, 0..100)
          anomaly_confidence_label   (str)
          severity                   ("Low" | "Medium" | "High" | "Critical")
          severity_reason            (str)
        The input is NOT mutated.

    Ground-truth columns (is_anomaly, anomaly_type,
    injected_parameter) are NOT used for scoring.
    """
    if config is None:
        config = ScoringConfig()

    out = df.copy()
    n = len(out)

    # ---- Extract evidence-source flags (safe, missing → 0) ----
    if_flag = _safe_int_arr(out, "predicted_anomaly", n)
    qc_any = _safe_int_arr(out, "qc_any_flag", n)
    spatial_iso = _safe_int_arr(out, "spatial_isolated_flag", n)
    temporal_pred = _safe_int_arr(out, "temporal_predicted_anomaly", n)

    # ---- Categorical confidence from classifier (optional) ----
    categorical_conf = _safe_str_arr(out, "anomaly_class_confidence", n)

    # ---- Confidence ----
    confidence, conf_labels = _compute_confidence(
        if_flag, qc_any, spatial_iso, temporal_pred,
        categorical_conf, config,
    )

    # ---- Severity inputs ----
    z4 = _safe_float_arr(out, "temporal_z_4", n)
    z8 = _safe_float_arr(out, "temporal_z_8", n)
    z16 = _safe_float_arr(out, "temporal_z_16", n)

    temporal_l2 = _safe_int_arr(out, "temporal_level2_flag", n)
    qc_persistence = _safe_int_arr(out, "qc_persistence_flag", n)
    qc_temporal = _safe_int_arr(out, "qc_temporal_flag", n)
    qc_range = _safe_int_arr(out, "qc_range_flag", n)
    qc_internal = _safe_int_arr(out, "qc_internal_flag", n)
    spatial_com = _safe_int_arr(out, "spatial_common_event_flag", n)

    # ---- Severity ----
    severity, severity_reasons = _compute_severity(
        z4, z8, z16,
        temporal_l2, qc_persistence, qc_temporal,
        qc_range, qc_internal,
        spatial_iso, spatial_com,
        if_flag, qc_any, temporal_pred,
        config,
    )

    # ---- Assign output columns ----
    out["anomaly_confidence"] = confidence
    out["anomaly_confidence_label"] = conf_labels
    out["severity"] = severity
    out["severity_reason"] = severity_reasons

    return out


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    # Sibling import shim.
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402
    from qc_rules import apply_qc_rules  # noqa: E402
    from spatial_analysis import apply_spatial_analysis  # noqa: E402
    from temporal_detector import apply_temporal_detector  # noqa: E402
    from anomaly_classifier import classify_anomalies  # noqa: E402

    print("=" * 70)
    print("SkyGuard AI - STEP 18: Confidence + Severity Scoring (demo)")
    print("=" * 70)

    # 1. Load test data.
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])
    print(f"\nLoaded observations: {len(obs)} rows")

    # 2. Build features + QC.
    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()
    print(f"QC flags computed: {len(qc)} rows")

    # 3. Spatial analysis (suppress neighbour graph print).
    metadata_path = "data/station_metadata.csv"
    spatial = None
    if os.path.exists(metadata_path):
        metadata = pd.read_csv(metadata_path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            spatial = apply_spatial_analysis(obs, metadata)
        spatial_cols = ["station_id", "timestamp"] + [
            c for c in spatial.columns if c.startswith("spatial_")
        ]
        spatial = spatial[spatial_cols].copy()
        print(f"Spatial flags computed: {len(spatial)} rows")
    else:
        print("[SKIP] station_metadata.csv not found; spatial skipped")

    # 4. Temporal detector.
    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()
    print(f"Temporal flags computed: {len(temporal)} rows")

    # 5. Load IF predictions.
    if_path = "data/isolation_forest_predictions.csv"
    if_df = pd.read_csv(if_path)
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()
    print(f"IF predictions loaded: {len(if_df)} rows")

    # 6. Join all sources.
    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    if spatial is not None:
        joined = joined.merge(
            spatial, on=["station_id", "timestamp"], how="left"
        )
    joined = joined.merge(
        temporal, on=["station_id", "timestamp"], how="left"
    )
    print(f"Joined DataFrame: {len(joined)} rows, {len(joined.columns)} cols")

    # 7. Run classifier (for categorical confidence).
    classified = classify_anomalies(joined)
    print(f"Classification done: {len(classified)} rows")

    # 8. Run scoring.
    result = score_anomalies(classified)
    print(f"Scoring done: {len(result)} rows")

    # 9. Print diagnostics.
    print(f"\n--- Total rows: {len(result)} ---")

    # Confidence distribution.
    conf = result["anomaly_confidence"]
    print(f"\n--- Confidence distribution ---")
    print(f"  Min:    {conf.min()}")
    print(f"  Median: {int(conf.median())}")
    print(f"  Max:    {conf.max()}")

    # Confidence histogram (10-point buckets).
    print(f"\n--- Confidence histogram (10-point buckets) ---")
    buckets = np.arange(0, 101, 10)
    hist, _ = np.histogram(conf, bins=buckets)
    for j in range(len(hist)):
        lo = buckets[j]
        hi = buckets[j + 1]
        print(f"  {lo:>3d}-{hi:>3d}: {'#' * hist[j]:<30s}  {hist[j]:>6d}")

    # Severity distribution.
    print(f"\n--- Severity distribution ---")
    print(result["severity"].value_counts().to_string())

    # 5 example rows.
    print(f"\n--- 5 example rows ---")
    # Pick rows with variety: try to get at least one of each severity.
    example_indices = []
    for sev in ["Critical", "High", "Medium", "Low"]:
        sub = result[result["severity"] == sev]
        if len(sub) > 0:
            example_indices.append(sub.index[0])
    # Fill remaining slots.
    remaining = [i for i in result.index if i not in example_indices]
    while len(example_indices) < 5 and remaining:
        example_indices.append(remaining.pop(0))

    cols_show = [
        "timestamp", "station_id", "anomaly_class",
        "anomaly_confidence", "anomaly_confidence_label",
        "severity", "severity_reason",
    ]
    available = [c for c in cols_show if c in result.columns]
    for line in result.loc[example_indices[:5]][available].to_string(
        index=False, max_colwidth=80
    ).splitlines():
        print("  " + line)