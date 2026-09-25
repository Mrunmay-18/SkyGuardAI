"""
diagnostics/diagnose_missed_anomalies.py
SkyGuard AI - STEP 16-D: Diagnostic for IF false negatives.

READ-ONLY diagnostic that analyzes the anomaly rows the Isolation
Forest baseline missed (IF false negatives) and checks whether QC
rules or spatial analysis can recover them.

Does NOT:
  - change any threshold
  - tune any parameter
  - retrain or modify any model
  - modify any CSV
  - create a new detector
  - modify evidence_fusion.py

QC flags and spatial flags are NOT saved to CSV in this project; they
are computed at runtime via apply_qc_rules() and apply_spatial_analysis()
respectively. This script never fabricates filenames — if a file is
missing, it either computes the data from code or skips the check with
a clear note.

Usage:
    python diagnostics/diagnose_missed_anomalies.py
"""

import contextlib
import io
import os
import sys

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
IF_PREDICTIONS_PATH = "data/isolation_forest_predictions.csv"
TEST_DATA_PATH = "data/test_injected_aws.csv"
METADATA_PATH = "data/station_metadata.csv"

OUTPUT_DIR = "diagnostics"
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "missed_anomaly_diagnosis.txt")

# Sibling src/ directory for importing feature_engineering, qc_rules,
# spatial_analysis.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ----------------------------------------------------------------------
# Load + compute helpers
# ----------------------------------------------------------------------
def _load_inputs():
    """Load IF predictions and test data."""
    if not os.path.exists(IF_PREDICTIONS_PATH):
        raise FileNotFoundError(
            f"IF predictions not found: {IF_PREDICTIONS_PATH}. "
            "Run src/ml_detector.py first."
        )
    if not os.path.exists(TEST_DATA_PATH):
        raise FileNotFoundError(
            f"Test data not found: {TEST_DATA_PATH}. "
            "Run generator.py + injector.py first."
        )
    if_df = pd.read_csv(IF_PREDICTIONS_PATH)
    obs_df = pd.read_csv(TEST_DATA_PATH)
    return if_df, obs_df


def _compute_qc_flags(obs_df):
    """
    Compute QC flags at runtime via build_features + apply_qc_rules.
    Returns a DataFrame with qc_* columns + join keys.
    """
    from feature_engineering import build_features
    from qc_rules import apply_qc_rules

    feats = build_features(obs_df)
    qc_df = apply_qc_rules(feats)
    # Keep only qc_* columns + join keys (don't duplicate obs columns).
    keep = ["station_id", "timestamp"] + [
        c for c in qc_df.columns if c.startswith("qc_")
    ]
    return qc_df[keep].copy()


def _compute_spatial_flags(obs_df):
    """
    Compute spatial flags at runtime via apply_spatial_analysis.

    Returns (spatial_df, status_msg). If station_metadata.csv is
    missing, returns (None, skip_message) — the caller logs the skip.
    """
    if not os.path.exists(METADATA_PATH):
        return None, (f"[SKIP] spatial analysis not available "
                      f"(metadata not found: {METADATA_PATH})")

    from spatial_analysis import (
        apply_spatial_analysis, _compute_station_baselines,
        DEFAULT_NORMAL_CSV,
    )

    metadata_df = pd.read_csv(METADATA_PATH)
    station_ids = metadata_df["station_id"].tolist()
    baselines = _compute_station_baselines(DEFAULT_NORMAL_CSV, station_ids)

    # Suppress the neighbour-graph print to keep diagnostic output clean.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spatial_df = apply_spatial_analysis(
            obs_df, metadata_df, baselines=baselines
        )
    keep = ["station_id", "timestamp"] + [
        c for c in spatial_df.columns if c.startswith("spatial_")
    ]
    return spatial_df[keep].copy(), "spatial flags computed"


# ----------------------------------------------------------------------
# Main diagnostic
# ----------------------------------------------------------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Capture all output for the text file.
    output_lines = []

    def log(msg=""):
        print(msg)
        output_lines.append(msg)

    log("=" * 70)
    log("SkyGuard AI - STEP 16-D: IF False Negative Diagnostic")
    log("=" * 70)

    # 1. Load inputs.
    if_df, obs_df = _load_inputs()
    log(f"\nLoaded IF predictions: {len(if_df)} rows from {IF_PREDICTIONS_PATH}")
    log(f"Loaded test data:      {len(obs_df)} rows from {TEST_DATA_PATH}")

    # 2. Identify IF false negatives.
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    fn_mask = (if_df["is_anomaly"] == 1) & (if_df["predicted_anomaly"] == 0)
    fn_df = if_df[fn_mask].copy()
    log(f"\nIF false negatives (is_anomaly=1 AND predicted_anomaly=0): "
        f"{len(fn_df)} rows")

    # 3. Compute QC flags at runtime.
    log("\nComputing QC flags at runtime via apply_qc_rules()...")
    qc_df = _compute_qc_flags(obs_df)
    qc_df["timestamp"] = pd.to_datetime(qc_df["timestamp"])
    log(f"  QC flags computed: {len(qc_df)} rows")

    # 4. Compute spatial flags at runtime (skip gracefully if metadata missing).
    log("\nComputing spatial flags at runtime via apply_spatial_analysis()...")
    spatial_df, spatial_status = _compute_spatial_flags(obs_df)
    log(f"  {spatial_status}")
    if spatial_df is not None:
        spatial_df["timestamp"] = pd.to_datetime(spatial_df["timestamp"])

    # 5. Join false negatives with QC and spatial on (station_id, timestamp).
    joined = fn_df.merge(qc_df, on=["station_id", "timestamp"], how="left")
    if spatial_df is not None:
        joined = joined.merge(
            spatial_df, on=["station_id", "timestamp"], how="left"
        )

    # Fill NaN flags with 0 and note any missing columns.
    flag_cols = [
        "qc_range_flag", "qc_temporal_flag", "qc_persistence_flag",
        "qc_internal_flag", "qc_gap_flag", "qc_any_flag",
        "spatial_isolated_flag", "spatial_common_event_flag",
    ]
    for col in flag_cols:
        if col not in joined.columns:
            joined[col] = 0
            log(f"  [NOTE] {col} not available; treating as 0")
        else:
            joined[col] = joined[col].fillna(0).astype(int)

    # 6. Define RECOVERABLE = qc_any_flag==1 OR spatial_isolated_flag==1.
    # spatial_common_event_flag does NOT count (counter-evidence, not fault evidence).
    joined["recoverable"] = (
        (joined["qc_any_flag"] == 1) | (joined["spatial_isolated_flag"] == 1)
    ).astype(int)

    # 7. Summary table.
    log("\n" + "-" * 70)
    log("Evidence coverage among IF false negatives")
    log("-" * 70)
    n_fn = len(joined)
    n_recoverable = int(joined["recoverable"].sum())
    n_qc = int((joined["qc_any_flag"] == 1).sum())
    n_qc_range = int((joined["qc_range_flag"] == 1).sum())
    n_qc_temporal = int((joined["qc_temporal_flag"] == 1).sum())
    n_qc_persistence = int((joined["qc_persistence_flag"] == 1).sum())
    n_qc_internal = int((joined["qc_internal_flag"] == 1).sum())
    n_qc_gap = int((joined["qc_gap_flag"] == 1).sum())
    n_spatial_iso = int((joined["spatial_isolated_flag"] == 1).sum())
    n_spatial_com = int((joined["spatial_common_event_flag"] == 1).sum())

    log(f"Total IF false negatives:                      {n_fn}")
    log(f"Recoverable by ANY non-IF evidence:              {n_recoverable}")
    log(f"QC catches (qc_any_flag == 1):                   {n_qc}")
    log(f"  - qc_range_flag:                               {n_qc_range}")
    log(f"  - qc_temporal_flag:                            {n_qc_temporal}")
    log(f"  - qc_persistence_flag:                          {n_qc_persistence}")
    log(f"  - qc_internal_flag:                            {n_qc_internal}")
    log(f"  - qc_gap_flag:                                 {n_qc_gap}")
    log(f"Spatial isolated catches:                        {n_spatial_iso}")
    log(f"Spatial common-event rows (counter-evidence):    {n_spatial_com}")

    # 8. Per-anomaly-type table.
    log("\n" + "-" * 70)
    log("Per-anomaly-type breakdown")
    log("-" * 70)

    type_stats = []
    for atype, g in joined.groupby("anomaly_type"):
        type_stats.append({
            "anomaly_type": atype,
            "total_missed": len(g),
            "recoverable": int(g["recoverable"].sum()),
            "qc_range": int((g["qc_range_flag"] == 1).sum()),
            "qc_temporal": int((g["qc_temporal_flag"] == 1).sum()),
            "qc_persistence": int((g["qc_persistence_flag"] == 1).sum()),
            "qc_internal": int((g["qc_internal_flag"] == 1).sum()),
            "qc_gap": int((g["qc_gap_flag"] == 1).sum()),
            "spatial_isolated": int((g["spatial_isolated_flag"] == 1).sum()),
        })
    type_df = pd.DataFrame(type_stats).sort_values(
        "total_missed", ascending=False
    ).reset_index(drop=True)

    # Print aligned table.
    header = (
        f"  {'anomaly_type':<30s}  {'missed':>7s}  {'recov':>7s}  "
        f"{'range':>6s}  {'temp':>6s}  {'persist':>8s}  "
        f"{'intern':>7s}  {'gap':>5s}  {'sp_iso':>7s}"
    )
    log(header)
    log("  " + "-" * (len(header) - 2))
    for _, r in type_df.iterrows():
        log(
            f"  {str(r['anomaly_type']):<30s}  "
            f"{int(r['total_missed']):>7d}  {int(r['recoverable']):>7d}  "
            f"{int(r['qc_range']):>6d}  {int(r['qc_temporal']):>6d}  "
            f"{int(r['qc_persistence']):>8d}  "
            f"{int(r['qc_internal']):>7d}  {int(r['qc_gap']):>5d}  "
            f"{int(r['spatial_isolated']):>7d}"
        )

    # 9. Example RECOVERED rows.
    log("\n" + "-" * 70)
    log("Example RECOVERED IF false negatives (non-IF evidence catches them)")
    log("-" * 70)
    recovered = joined[joined["recoverable"] == 1].head(5)
    if recovered.empty:
        log("  (none)")
    else:
        for _, row in recovered.iterrows():
            evidence_parts = []
            if row["qc_range_flag"]:
                evidence_parts.append("qc_range")
            if row["qc_temporal_flag"]:
                evidence_parts.append("qc_temporal")
            if row["qc_persistence_flag"]:
                evidence_parts.append("qc_persistence")
            if row["qc_internal_flag"]:
                evidence_parts.append("qc_internal")
            if row["qc_gap_flag"]:
                evidence_parts.append("qc_gap")
            if row["spatial_isolated_flag"]:
                evidence_parts.append("spatial_isolated")
            log(f"  {row['timestamp']}  {row['station_id']}  "
                f"{row['anomaly_type']:<30s}  "
                f"evidence: {', '.join(evidence_parts)}")

    # 10. Example UNRECOVERED rows.
    log("\n" + "-" * 70)
    log("Example UNRECOVERED IF false negatives (no non-IF evidence catches them)")
    log("-" * 70)
    unrecovered = joined[joined["recoverable"] == 0].head(5)
    if unrecovered.empty:
        log("  (none - all IF false negatives are recoverable)")
    else:
        for _, row in unrecovered.iterrows():
            log(f"  {row['timestamp']}  {row['station_id']}  "
                f"{row['anomaly_type']}")

    # 11. Conclusion.
    log("\n" + "=" * 70)
    log("CONCLUSION")
    log("=" * 70)

    pct_qc = 100.0 * n_qc / n_fn if n_fn > 0 else 0.0
    pct_spatial = 100.0 * n_spatial_iso / n_fn if n_fn > 0 else 0.0
    pct_recoverable = 100.0 * n_recoverable / n_fn if n_fn > 0 else 0.0

    log(f"\nA. How many IF false negatives are recoverable using EXISTING QC evidence?")
    log(f"   {n_qc} out of {n_fn} ({pct_qc:.1f}%) are recoverable by QC rules.")

    log(f"\nB. How many are recoverable using EXISTING spatial evidence?")
    log(f"   {n_spatial_iso} out of {n_fn} ({pct_spatial:.1f}%) are recoverable "
        f"by spatial isolated-deviation.")

    log(f"\nC. Which anomaly types remain almost completely undetected even "
        f"with all current evidence?")
    # Types with 0 recoverable.
    zero_recov = type_df[type_df["recoverable"] == 0]
    if not zero_recov.empty:
        for _, r in zero_recov.iterrows():
            log(f"   {r['anomaly_type']}: 0/{int(r['total_missed'])} recoverable "
                f"(0.0%).")
    # Types with low recovery (<50%).
    low_recov = type_df[
        (type_df["recoverable"] > 0) &
        (type_df["recoverable"] / type_df["total_missed"] < 0.5)
    ]
    for _, r in low_recov.iterrows():
        pct = 100.0 * r["recoverable"] / r["total_missed"]
        log(f"   {r['anomaly_type']}: {int(r['recoverable'])}/"
            f"{int(r['total_missed'])} ({pct:.1f}%) recoverable.")

    log(f"\nD. Does the current evidence justify changing the fusion layer, "
        f"or does the evidence indicate that an upstream detector needs "
        f"improvement?")
    # Find the biggest contributor to misses.
    biggest = type_df.iloc[0]
    pct_biggest = 100.0 * biggest["total_missed"] / n_fn if n_fn > 0 else 0.0
    pct_big_recov = (
        100.0 * biggest["recoverable"] / biggest["total_missed"]
        if biggest["total_missed"] > 0 else 0.0
    )
    log(f"   The biggest contributor to IF false negatives is "
        f"{biggest['anomaly_type']} "
        f"({int(biggest['total_missed'])}/{n_fn} = {pct_biggest:.1f}% "
        f"of all misses).")
    log(f"   Of those, only {int(biggest['recoverable'])}/"
        f"{int(biggest['total_missed'])} ({pct_big_recov:.1f}%) are "
        f"recoverable by current QC+spatial evidence.")
    if pct_biggest > 50 and pct_big_recov < 50:
        log(f"   Since {pct_biggest:.1f}% of remaining misses are "
            f"{biggest['anomaly_type']}, and current detectors recover "
            f"only {pct_big_recov:.1f}% of those, no current detector "
            f"adequately addresses {biggest['anomaly_type']}.")
        if biggest["anomaly_type"] == "calibration_drift":
            log(f"   An upstream detector improvement is likely needed to "
                f"capture slow, gradual drift that the current per-row QC "
                f"and spatial evidence do not recover.")
        else:
            log(f"   An upstream detector improvement is needed for "
                f"{biggest['anomaly_type']}.")
        log(f"   The current evidence provides limited recovery for these "
            f"misses, so an upstream detector improvement should be "
            f"investigated before changing fusion weights.")
    else:
        log(f"   Current QC+spatial evidence recovers {n_recoverable}/{n_fn} "
            f"({pct_recoverable:.1f}%) of IF false negatives.")
        log(f"   The fusion layer could be adjusted to weight QC/spatial "
            f"evidence more heavily to recover these misses.")

    # Save to text file.
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n[SAVE] Diagnosis saved to {OUTPUT_TXT}")


if __name__ == "__main__":
    main()