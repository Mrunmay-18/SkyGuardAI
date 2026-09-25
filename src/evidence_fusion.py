"""
src/evidence_fusion.py
SkyGuard AI - STEP 17: Evidence Fusion Layer.

Combines outputs from the existing detectors into a single transparent
evidence score + plain-language explanation per row.

Detectors consumed:
  1. ML anomaly detection (Isolation Forest)
       Source: data/isolation_forest_predictions.csv
       Columns: predicted_anomaly (0/1), anomaly_score

  2. Rule-based QC engine (src/qc_rules.py)
       Source: apply_qc_rules() at runtime
       Columns: qc_any_flag, plus individual flags for explanation

  3. Spatial consistency (src/spatial_analysis.py)
       Source: apply_spatial_analysis() at runtime
       Columns: spatial_isolated_flag (fault evidence),
                spatial_common_event_flag (counter-evidence)

  4. Temporal autoencoder (OPTIONAL, not yet implemented)
       Source: data/autoencoder_predictions.csv (if it exists)
       Column: ae_predicted_anomaly (0/1)
       If absent, the fusion skips AE gracefully (no crash).

IMPORTANT: This is a TRANSPARENT WEIGHTED EVIDENCE score for a
prototype. It is NOT a calibrated probability and must never be
presented as one.

Uses only pandas and numpy. No sklearn, no ML.
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
class FusionConfig:
    """
    Transparent weighted evidence score for a prototype.
    NOT a calibrated probability. Intended to be inspected and
    adjusted by a meteorologist reviewing the individual contributing
    signals.

    All weights are PROTOTYPE HEURISTICS. A negative weight represents
    COUNTER-EVIDENCE (it lowers the fused score, suppressing false
    alarms on genuine weather events).
    """

    # ---- Fault-evidence weights (raise suspicion) ----
    WEIGHT_IF: float = 1.0                   # Isolation Forest
    WEIGHT_QC: float = 0.7                   # Rule-based QC engine
    WEIGHT_SPATIAL_ISOLATED: float = 1.2     # Spatial isolated deviation
    WEIGHT_AE: float = 1.0                   # Autoencoder (optional)

    # ---- Counter-evidence weight (lowers suspicion) ----
    WEIGHT_SPATIAL_COMMON_EVENT: float = -0.8  # Spatial common event = weather

    # ---- Decision thresholds ----
    SCORE_HIGH: float = 2.0
    SCORE_MEDIUM: float = 1.0


# ----------------------------------------------------------------------
# Helper: extract variable name from spatial reason strings
# ----------------------------------------------------------------------
def _extract_spatial_variable(reason: str, prefix: str) -> str:
    """
    Extract the variable name from a spatial reason string.

    Isolated reason format:
        "isolated spatial anomaly: temperature=31.8 (z=1.6) vs ..."
    Common-event reason format:
        "common event: temperature change 5.2 matches ..."
    """
    if not reason or not isinstance(reason, str):
        return "unknown"
    idx = reason.find(prefix)
    if idx < 0:
        return "unknown"
    rest = reason[idx + len(prefix):]
    # Variable is the first token before '=' (isolated) or ' change' (common event).
    if "=" in rest:
        return rest.split("=")[0].strip()
    if " change" in rest:
        return rest.split(" change")[0].strip()
    return "unknown"


def _extract_target_z(reason: str) -> str:
    """Extract the target's z-score from an isolated reason string."""
    if not reason or not isinstance(reason, str):
        return ""
    # Format: "... temperature=31.8 (z=1.6) vs neighbours ..."
    idx = reason.find("(z=")
    if idx < 0:
        return ""
    rest = reason[idx + 3:]
    end = rest.find(")")
    if end < 0:
        return ""
    return rest[:end]


def _extract_qc_rules_fired(qc_reasons: str) -> list:
    """
    Determine which QC rules fired from the qc_reasons string.
    Returns a list of short rule names.
    """
    if not qc_reasons or not isinstance(qc_reasons, str):
        return []
    qr = qc_reasons.lower()
    fired = []
    if "out of range" in qr or "out of [0,100]" in qr:
        fired.append("range")
    if "large change" in qr:
        fired.append("temporal")
    if "frozen for" in qr:
        fired.append("persistence")
    if "dew point" in qr or "isolated" in qr:
        fired.append("internal")
    if "gap of" in qr:
        fired.append("gap")
    return fired


# ----------------------------------------------------------------------
# Explanation builders
# ----------------------------------------------------------------------
def _build_explanation(anomaly_score, qc_reasons, spatial_iso_reason,
                       spatial_com_reason, if_flag, qc_flag, spatial_iso,
                       spatial_com, ae_flag, score, label, config):
    """Build the full human-readable explanation string."""
    # ---- Contradictory case (handled BEFORE thresholding) ----
    if label == "contradictory":
        iso_var = _extract_spatial_variable(
            spatial_iso_reason, "isolated spatial anomaly: ")
        com_var = _extract_spatial_variable(
            spatial_com_reason, "common event: ")
        iso_z = _extract_target_z(spatial_iso_reason)
        z_info = f" (z={iso_z} vs neighbours)" if iso_z else ""
        return (
            f"Spatial evidence contradictory: isolated on {iso_var}{z_info} "
            f"AND common event on {com_var}. -> manual review recommended"
        )

    # ---- Normal case ----
    parts = []

    if if_flag:
        if pd.notna(anomaly_score):
            parts.append(f"IF flagged (score={anomaly_score:.2f})")
        else:
            parts.append("IF flagged")

    if qc_flag:
        fired = _extract_qc_rules_fired(qc_reasons)
        if fired:
            parts.append(f"QC fired: {', '.join(fired)}")
        else:
            parts.append("QC fired")

    if spatial_iso:
        iso_var = _extract_spatial_variable(
            spatial_iso_reason, "isolated spatial anomaly: ")
        parts.append(f"Spatial: isolated on {iso_var}")

    if ae_flag:
        parts.append("AE flagged")

    if spatial_com:
        # Extract the detail after "common event: ".
        if spatial_com_reason and "common event:" in spatial_com_reason:
            detail = spatial_com_reason.split("common event: ", 1)[1]
            parts.append(f"Spatial: common event ({detail})")
        else:
            parts.append("Spatial: common event")

    if not parts:
        return f"no evidence -> {label}"

    # Label suffix for weather-event cases.
    label_suffix = ""
    if label == "low" and spatial_com:
        label_suffix = ": possible genuine weather event"

    # Join parts with ". " and append the score/label.
    explanation = ". ".join(parts) + f". -> score={score:.1f} ({label}{label_suffix})"
    return explanation


def _build_short_explanation(if_flag, qc_flag, spatial_iso, spatial_com,
                              ae_flag, label):
    """Build the one-line short explanation for dashboard table rows."""
    if label == "contradictory":
        return "contradictory spatial evidence"

    parts = []
    if if_flag:
        parts.append("IF")
    if qc_flag:
        parts.append("QC")
    if spatial_iso:
        parts.append("spatial isolated")
    if ae_flag:
        parts.append("AE")

    if not parts:
        if spatial_com:
            return f"common event only -> {label} (weather)"
        return f"no evidence -> {label}"

    detectors = "+".join(parts)
    if len(parts) == 1:
        detectors += " only"

    if spatial_com:
        return f"{detectors} + common event -> {label} (weather)"

    return f"{detectors} -> {label}"


# ----------------------------------------------------------------------
# Main fusion function
# ----------------------------------------------------------------------
def fuse_evidence(joined_df: pd.DataFrame,
                  config: FusionConfig | None = None) -> pd.DataFrame:
    """
    Fuse evidence from all detectors into a single score + label +
    explanation per row.

    The input must be a pre-joined DataFrame containing (at minimum)
    the columns from the raw observations. Detector output columns
    (predicted_anomaly, qc_any_flag, spatial_isolated_flag,
    spatial_common_event_flag, ae_predicted_anomaly) are OPTIONAL —
    if a detector's output is missing, its contribution is treated as 0.

    Contradictory-evidence handling: if spatial_isolated_flag AND
    spatial_common_event_flag both fire on the same row, the label is
    "contradictory" (handled BEFORE thresholding), fused_any_flag is 0,
    and the explanation recommends manual review.

    Parameters
    ----------
    joined_df : pd.DataFrame
        Pre-joined observations with detector outputs.
    config : FusionConfig | None
        Optional configuration. Defaults to FusionConfig().

    Returns
    -------
    pd.DataFrame
        Copy of joined_df with ADDED columns:
          fused_score, fused_label, fused_any_flag,
          fused_evidence_count, fused_counter_evidence,
          fused_explanation, fused_explanation_short.
        The input is NOT mutated.
    """
    if config is None:
        config = FusionConfig()

    out = joined_df.copy()
    n = len(out)

    # ---- Extract detector flags (treat missing/NaN as 0) ----
    def _get_flag(col):
        if col in out.columns:
            return out[col].fillna(0).astype(int).to_numpy()
        return np.zeros(n, dtype=int)

    if_flag = _get_flag("predicted_anomaly")
    qc_flag = _get_flag("qc_any_flag")
    spatial_iso = _get_flag("spatial_isolated_flag")
    spatial_com = _get_flag("spatial_common_event_flag")
    ae_flag = _get_flag("ae_predicted_anomaly")

    # ---- Compute fused score (weighted sum) ----
    score = (
        config.WEIGHT_IF * if_flag
        + config.WEIGHT_QC * qc_flag
        + config.WEIGHT_SPATIAL_ISOLATED * spatial_iso
        + config.WEIGHT_AE * ae_flag
        + config.WEIGHT_SPATIAL_COMMON_EVENT * spatial_com
    )

    # ---- Contradictory evidence (spatial isolated AND common event) ----
    # Handled BEFORE thresholding per spec.
    contradictory = (spatial_iso == 1) & (spatial_com == 1)

    # ---- Determine labels ----
    # Vectorized: contradictory > high > medium > low > none.
    labels = np.where(contradictory, "contradictory",
               np.where(score >= config.SCORE_HIGH, "high",
               np.where(score >= config.SCORE_MEDIUM, "medium",
               np.where(score > 0, "low", "none"))))

    # ---- fused_any_flag: 1 only for high/medium (NOT contradictory, NOT low) ----
    fused_any = np.where(np.isin(labels, ["high", "medium"]), 1, 0)

    # ---- Evidence counts ----
    evidence_count = if_flag + qc_flag + spatial_iso + ae_flag  # 0..4
    counter_evidence = spatial_com  # 0 or 1

    # ---- Precompute arrays for explanation building ----
    anomaly_scores = (
        out["anomaly_score"].to_numpy() if "anomaly_score" in out.columns
        else np.full(n, np.nan)
    )
    qc_reasons_arr = (
        out["qc_reasons"].to_numpy() if "qc_reasons" in out.columns
        else np.array([""] * n, dtype=object)
    )
    spatial_iso_reasons = (
        out["spatial_isolated_reason"].to_numpy()
        if "spatial_isolated_reason" in out.columns
        else np.array([""] * n, dtype=object)
    )
    spatial_com_reasons = (
        out["spatial_common_event_reason"].to_numpy()
        if "spatial_common_event_reason" in out.columns
        else np.array([""] * n, dtype=object)
    )

    # ---- Build explanations (list comprehension for speed) ----
    explanations = [
        _build_explanation(
            anomaly_scores[i], qc_reasons_arr[i], spatial_iso_reasons[i],
            spatial_com_reasons[i], if_flag[i], qc_flag[i], spatial_iso[i],
            spatial_com[i], ae_flag[i], score[i], labels[i], config
        )
        for i in range(n)
    ]
    short_explanations = [
        _build_short_explanation(
            if_flag[i], qc_flag[i], spatial_iso[i], spatial_com[i],
            ae_flag[i], labels[i]
        )
        for i in range(n)
    ]

    # ---- Assign output columns ----
    out["fused_score"] = score
    out["fused_label"] = labels
    out["fused_any_flag"] = fused_any
    out["fused_evidence_count"] = evidence_count
    out["fused_counter_evidence"] = counter_evidence
    out["fused_explanation"] = explanations
    out["fused_explanation_short"] = short_explanations

    return out


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Sibling import shim.
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402
    from qc_rules import apply_qc_rules  # noqa: E402
    from spatial_analysis import (  # noqa: E402
        apply_spatial_analysis, _compute_station_baselines,
        DEFAULT_NORMAL_CSV, DEFAULT_METADATA_PATH,
    )

    print("=" * 70)
    print("SkyGuard AI - STEP 17: Evidence Fusion Layer (demo)")
    print("=" * 70)

    # 1. Load observations.
    obs_path = "data/test_injected_aws.csv"
    obs_df = pd.read_csv(obs_path)
    print(f"\nLoaded observations: {len(obs_df)} rows from {obs_path}")

    # 2. Load IF predictions (keep only unique columns + join keys).
    if_path = "data/isolation_forest_predictions.csv"
    if_df = pd.read_csv(if_path)
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()
    print(f"Loaded IF predictions: {len(if_df)} rows from {if_path}")

    # 3. Compute QC flags on the SAME observations.
    feats = build_features(obs_df)
    qc_df = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc_df.columns if c.startswith("qc_")
    ]
    qc_df = qc_df[qc_cols].copy()
    print(f"Computed QC flags: {len(qc_df)} rows")

    # 4. Try to compute spatial flags (skip gracefully if metadata missing).
    spatial_df = None
    if os.path.exists(DEFAULT_METADATA_PATH):
        metadata_df = pd.read_csv(DEFAULT_METADATA_PATH)
        station_ids = metadata_df["station_id"].tolist()
        baselines = _compute_station_baselines(DEFAULT_NORMAL_CSV, station_ids)
        spatial_df = apply_spatial_analysis(
            obs_df, metadata_df, baselines=baselines
        )
        spatial_cols = ["station_id", "timestamp"] + [
            c for c in spatial_df.columns if c.startswith("spatial_")
        ]
        spatial_df = spatial_df[spatial_cols].copy()
        print(f"Computed spatial flags: {len(spatial_df)} rows")
    else:
        print(f"[SKIP] Station metadata not found at {DEFAULT_METADATA_PATH}; "
              f"spatial analysis skipped.")

    # 5. Try to load AE predictions (skip gracefully if missing).
    ae_df = None
    ae_path = "data/autoencoder_predictions.csv"
    if os.path.exists(ae_path):
        ae_df = pd.read_csv(ae_path)
        ae_keep = ["station_id", "timestamp", "ae_predicted_anomaly"]
        ae_df = ae_df[[c for c in ae_keep if c in ae_df.columns]].copy()
        print(f"Loaded AE predictions: {len(ae_df)} rows from {ae_path}")
    else:
        print(f"[SKIP] AE predictions not found at {ae_path}; "
              f"autoencoder skipped (expected — AE not yet implemented).")

    # 6. Join all sources on (station_id, timestamp).
    joined = obs_df.copy()
    joined["timestamp"] = pd.to_datetime(joined["timestamp"])

    # Merge IF predictions.
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    joined = joined.merge(if_df, on=["station_id", "timestamp"], how="left")

    # Merge QC flags.
    qc_df["timestamp"] = pd.to_datetime(qc_df["timestamp"])
    joined = joined.merge(qc_df, on=["station_id", "timestamp"], how="left")

    # Merge spatial flags (if available).
    if spatial_df is not None:
        spatial_df["timestamp"] = pd.to_datetime(spatial_df["timestamp"])
        joined = joined.merge(spatial_df, on=["station_id", "timestamp"], how="left")

    # Merge AE predictions (if available).
    if ae_df is not None:
        ae_df["timestamp"] = pd.to_datetime(ae_df["timestamp"])
        joined = joined.merge(ae_df, on=["station_id", "timestamp"], how="left")

    print(f"\nJoined DataFrame: {len(joined)} rows, {len(joined.columns)} columns")

    # 7. Run fusion.
    result = fuse_evidence(joined)

    # 8. Print diagnostics.
    print(f"\nTotal rows: {len(result)}")

    print(f"\nDistribution of fused_label:")
    print(result["fused_label"].value_counts().to_string())

    print(f"\nDistribution of fused_any_flag:")
    print(result["fused_any_flag"].value_counts().to_string())

    # Cross-check vs ground-truth is_anomaly.
    if "is_anomaly" in result.columns:
        y_true = result["is_anomaly"].fillna(0).astype(int).to_numpy()
        y_pred = result["fused_any_flag"].to_numpy()
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        tn = int(((y_true == 0) & (y_pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
               if (precision + recall) > 0 else 0.0)
        print(f"\nCross-check vs is_anomaly (on fused_any_flag == 1):")
        print(f"  TP={tp}, FP={fp}, FN={fn}, TN={tn}")
        print(f"  Precision={precision:.4f}")
        print(f"  Recall   ={recall:.4f}")
        print(f"  F1       ={f1:.4f}")

    # Per-anomaly_type detection rate on fused_any_flag.
    if "anomaly_type" in result.columns:
        print(f"\nPer anomaly_type detection rate on fused_any_flag:")
        print(f"  {'anomaly_type':<30s}  {'detected':>10s}  {'total':>8s}  {'rate':>8s}")
        print("  " + "-" * 62)
        for atype, g in result.groupby("anomaly_type"):
            n_total = len(g)
            n_detected = int(g["fused_any_flag"].sum())
            rate = n_detected / n_total if n_total > 0 else 0.0
            print(f"  {str(atype):<30s}  {n_detected:>10d}  {n_total:>8d}  {rate:>7.1%}")

    # Count and top 5 contradictory rows.
    contra = result[result["fused_label"] == "contradictory"]
    print(f"\nContradictory rows: {len(contra)}")
    if len(contra) > 0:
        print("  Top 5 contradictory rows:")
        cols = ["timestamp", "station_id",
                "spatial_isolated_reason", "spatial_common_event_reason",
                "fused_explanation"]
        for line in contra.head(5)[cols].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            print("  " + line)

    # Top 5 rows by fused_score.
    print(f"\nTop 5 rows by fused_score (with explanations):")
    top5 = result.nlargest(5, "fused_score")
    cols = ["timestamp", "station_id", "fused_score", "fused_label",
            "fused_explanation_short"]
    for line in top5[cols].to_string(index=False, max_colwidth=100).splitlines():
        print("  " + line)

    # Rows with spatial_common_event_flag == 1 and their fused_label.
    if "spatial_common_event_flag" in result.columns:
        com = result[result["spatial_common_event_flag"].fillna(0) == 1]
        print(f"\nRows with spatial_common_event_flag=1: {len(com)}")
        if len(com) > 0:
            print("  (should mostly be 'none' or 'low' — counter-evidence)")
            cols = ["timestamp", "station_id", "fused_score", "fused_label",
                    "fused_explanation_short"]
            for line in com[cols].head(10).to_string(
                index=False, max_colwidth=100
            ).splitlines():
                print("  " + line)
    else:
        print("\n[SKIP] spatial_common_event_flag not available "
              "(spatial analysis was skipped).")