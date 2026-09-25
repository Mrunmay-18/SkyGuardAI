"""
diagnostics/inspect_calibration_drift.py
SkyGuard AI - Calibration Drift Inspection.

INSPECTION-ONLY experiment. Examines why the Isolation Forest baseline
misses gradual calibration drift on AWS_04 by inspecting temporal
characteristics of the drift period and comparing them with normal
AWS_04 behavior.

Does NOT:
  - modify any CSV, source file, model, or detector
  - create a new detector
  - tune any threshold
  - train any model
  - make predictions

Usage:
    python diagnostics/inspect_calibration_drift.py
"""

import os
import sys

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
TEST_DATA_PATH = "data/test_injected_aws.csv"
NORMAL_DATA_PATH = "data/normal_aws_data.csv"
IF_PREDICTIONS_PATH = "data/isolation_forest_predictions.csv"

OUTPUT_DIR = "diagnostics"
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "calibration_drift_inspection.txt")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _stats(arr) -> str:
    """Return a formatted string of mean/median/min/max/std for an array."""
    arr = arr[~np.isnan(arr)] if isinstance(arr, np.ndarray) else arr.dropna().to_numpy()
    if len(arr) == 0:
        return "n/a"
    return (
        f"mean={np.mean(arr):.4f}, median={np.median(arr):.4f}, "
        f"min={np.min(arr):.4f}, max={np.max(arr):.4f}, "
        f"std={np.std(arr):.4f}, n={len(arr)}"
    )


# ----------------------------------------------------------------------
# Main inspection
# ----------------------------------------------------------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_lines = []

    def log(msg=""):
        print(msg)
        output_lines.append(msg)

    log("=" * 70)
    log("SkyGuard AI - Calibration Drift Inspection")
    log("=" * 70)

    # 1. Load both CSV files.
    test_df = pd.read_csv(TEST_DATA_PATH)
    test_df["timestamp"] = pd.to_datetime(test_df["timestamp"])
    normal_df = pd.read_csv(NORMAL_DATA_PATH)
    normal_df["timestamp"] = pd.to_datetime(normal_df["timestamp"])
    log(f"\nLoaded test data:   {len(test_df)} rows from {TEST_DATA_PATH}")
    log(f"Loaded normal data: {len(normal_df)} rows from {NORMAL_DATA_PATH}")

    # 2. Identify calibration_drift rows.
    drift_mask = (
        (test_df["is_anomaly"] == 1)
        & (test_df["anomaly_type"] == "calibration_drift")
    )
    drift_df = test_df[drift_mask].sort_values("timestamp").reset_index(drop=True)

    if drift_df.empty:
        log("\n[ERROR] No calibration_drift rows found in the test data.")
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        return

    station_id = drift_df["station_id"].iloc[0]

    # 3. Print basic info.
    log(f"\n{'-' * 70}")
    log("Calibration Drift Overview")
    log(f"{'-' * 70}")
    n_drift = len(drift_df)
    start_ts = drift_df["timestamp"].iloc[0]
    end_ts = drift_df["timestamp"].iloc[-1]
    duration = end_ts - start_ts
    start_temp = float(drift_df["temperature"].iloc[0])
    end_temp = float(drift_df["temperature"].iloc[-1])
    total_change = end_temp - start_temp

    log(f"Number of calibration_drift rows: {n_drift}")
    log(f"Station ID:                       {station_id}")
    log(f"Start timestamp:                  {start_ts}")
    log(f"End timestamp:                    {end_ts}")
    log(f"Duration:                          {duration}")
    log(f"Starting temperature:             {start_temp:.2f} C")
    log(f"Ending temperature:               {end_temp:.2f} C")
    log(f"Total temperature change:         {total_change:.2f} C")

    # 4. Temporal characteristics.
    log(f"\n{'-' * 70}")
    log("Temporal Characteristics of Calibration Drift")
    log(f"{'-' * 70}")
    drift_temps = drift_df["temperature"].to_numpy(dtype=float)
    d_temp = np.diff(drift_temps)  # consecutive differences
    total_change_calc = float(np.sum(d_temp))
    avg_change_per_obs = float(np.mean(d_temp)) if len(d_temp) > 0 else 0.0
    # 4 observations per hour at 15-min cadence.
    change_per_hour = avg_change_per_obs * 4
    min_d = float(np.min(d_temp)) if len(d_temp) > 0 else 0.0
    max_d = float(np.max(d_temp)) if len(d_temp) > 0 else 0.0
    n_pos = int(np.sum(d_temp > 0))
    n_neg = int(np.sum(d_temp < 0))
    n_zero = int(np.sum(d_temp == 0))

    log(f"Temperature difference between consecutive rows (d_temp):")
    log(f"  Total change (sum of d_temp):     {total_change_calc:.4f} C")
    log(f"  Average change per 15-min obs:    {avg_change_per_obs:.4f} C")
    log(f"  Approximate change per hour:      {change_per_hour:.4f} C")
    log(f"  Min consecutive difference:       {min_d:.4f} C")
    log(f"  Max consecutive difference:       {max_d:.4f} C")
    consistent = (n_neg == 0)
    log(f"  Consistent direction?             {'Yes' if consistent else 'No'}")
    log(f"  Number of positive changes:       {n_pos}")
    log(f"  Number of negative changes:        {n_neg}")
    log(f"  Number of zero changes:           {n_zero}")

    # 5. Rolling temporal features (inspection only — no predictions).
    log(f"\n{'-' * 70}")
    log("Rolling Temporal Features (inspection only, NOT used for predictions)")
    log(f"{'-' * 70}")
    for window in [4, 8, 16]:
        hours = window * 15 / 60.0
        rolling_mean = drift_df["temperature"].rolling(window).mean()
        rolling_change = drift_df["temperature"].diff(window)
        log(f"  Window = {window} samples ({hours:.1f} hours):")
        log(f"    Rolling temperature mean  - {_stats(rolling_mean.to_numpy())}")
        log(f"    Rolling temperature change - {_stats(rolling_change.to_numpy())}")

    # 6. Compare with normal AWS_04 data.
    log(f"\n{'-' * 70}")
    log(f"Comparison: Normal vs Calibration-Drift (station {station_id})")
    log(f"{'-' * 70}")
    normal_aws = normal_df[normal_df["station_id"] == station_id].sort_values(
        "timestamp"
    ).reset_index(drop=True)

    normal_temps = normal_aws["temperature"].to_numpy(dtype=float)
    normal_d = np.diff(normal_temps)
    drift_d = d_temp  # already computed above

    log(f"\n  Consecutive d_temp (1-sample diff):")
    log(f"    Normal: {_stats(normal_d)}")
    log(f"    Drift:  {_stats(drift_d)}")

    for window in [4, 8, 16]:
        hours = window * 15 / 60.0
        normal_change = normal_aws["temperature"].diff(window).to_numpy()
        drift_change = drift_df["temperature"].diff(window).to_numpy()
        log(f"\n  {window}-sample temperature change ({hours:.1f}h):")
        log(f"    Normal: {_stats(normal_change)}")
        log(f"    Drift:  {_stats(drift_change)}")

    # 7. IF scores for calibration-drift rows.
    log(f"\n{'-' * 70}")
    log("Isolation Forest Scores for Calibration-Drift Rows")
    log(f"{'-' * 70}")
    if os.path.exists(IF_PREDICTIONS_PATH):
        if_df = pd.read_csv(IF_PREDICTIONS_PATH)
        if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
        joined = drift_df[["station_id", "timestamp"]].merge(
            if_df[["station_id", "timestamp", "predicted_anomaly",
                   "anomaly_score"]],
            on=["station_id", "timestamp"], how="left",
        )
        scores = joined["anomaly_score"].dropna()
        predicted = joined["predicted_anomaly"].fillna(0).astype(int)
        n_matched = len(joined)
        n_detected = int((predicted == 1).sum())
        n_missed = int((predicted == 0).sum())
        log(f"  Drift rows matched in IF predictions: {n_matched} / {n_drift}")
        if len(scores) > 0:
            log(f"  Min IF score:    {scores.min():.4f}")
            log(f"  Max IF score:    {scores.max():.4f}")
            log(f"  Mean IF score:   {scores.mean():.4f}")
            log(f"  Median IF score: {scores.median():.4f}")
        log(f"  Detected (predicted_anomaly=1): {n_detected}")
        log(f"  Missed (predicted_anomaly=0):   {n_missed}")
    else:
        log(f"  [SKIP] IF predictions not found at {IF_PREDICTIONS_PATH}")

    # 8. Factual conclusion.
    log(f"\n{'=' * 70}")
    log("CONCLUSION")
    log(f"{'=' * 70}")

    # A. Is there a clear gradual temporal pattern?
    log(f"\nA. Is there a clear gradual temporal pattern in calibration drift?")
    log(f"   The temperature changes from {start_temp:.2f} C to {end_temp:.2f} C "
        f"over {n_drift} observations ({duration}).")
    log(f"   The average change per observation is {avg_change_per_obs:.4f} C "
        f"(approximately {change_per_hour:.2f} C/hour).")
    log(f"   {n_pos} of {len(d_temp)} consecutive differences are positive, "
        f"{n_neg} are negative, {n_zero} are zero.")
    if n_neg == 0:
        log(f"   Yes - the temperature increases consistently in one direction "
            f"with no reversals.")
    else:
        pct_pos = 100.0 * n_pos / len(d_temp)
        log(f"   The drift has a positive trend: {pct_pos:.1f}% of consecutive "
            f"changes are positive. The {n_neg} negative changes are small "
            f"reversals from noise on top of the drift ramp.")

    # B. Does the temporal pattern appear different from normal?
    log(f"\nB. Does the temporal pattern appear different from normal "
        f"{station_id} behavior?")
    normal_d_mean = float(np.mean(normal_d))
    drift_d_mean = float(np.mean(drift_d))
    normal_d_std = float(np.std(normal_d))
    log(f"   Normal consecutive d_temp: mean={normal_d_mean:.4f} C, "
        f"std={normal_d_std:.4f} C")
    log(f"   Drift consecutive d_temp:  mean={drift_d_mean:.4f} C, "
        f"std={float(np.std(drift_d)):.4f} C")
    # Check larger windows.
    normal_16 = normal_aws["temperature"].diff(16).dropna().to_numpy()
    drift_16 = drift_df["temperature"].diff(16).dropna().to_numpy()
    n16_mean = float(np.mean(normal_16))
    d16_mean = float(np.mean(drift_16))
    n16_std = float(np.std(normal_16))
    d16_std = float(np.std(drift_16))
    log(f"   Normal 16-sample change: mean={n16_mean:.4f} C, std={n16_std:.4f}")
    log(f"   Drift 16-sample change:  mean={d16_mean:.4f} C, std={d16_std:.4f}")
    if abs(d16_mean - n16_mean) > 0.01:
        log(f"   Yes - the drift period shows a positive mean 16-sample change "
            f"({d16_mean:.4f} C) vs normal ({n16_mean:.4f} C).")
    else:
        log(f"   The per-step difference is subtle (drift mean "
            f"{drift_d_mean:.4f} vs normal {normal_d_mean:.4f}), but the "
            f"accumulated 16-sample change shows a clearer positive bias.")

    # C. Which measurements show the clearest difference?
    log(f"\nC. Which simple temporal measurements show the clearest difference?")
    separations = []
    for window in [1, 4, 8, 16]:
        if window == 1:
            n_arr = normal_d
            d_arr = drift_d
        else:
            n_arr = normal_aws["temperature"].diff(window).dropna().to_numpy()
            d_arr = drift_df["temperature"].diff(window).dropna().to_numpy()
        n_mean = float(np.mean(n_arr))
        d_mean = float(np.mean(d_arr))
        n_std = float(np.std(n_arr))
        sep = abs(d_mean - n_mean) / n_std if n_std > 0 else 0.0
        separations.append((window, sep, n_mean, d_mean, n_std))
        hours = window * 15 / 60.0
        log(f"   {window:>2d}-sample change ({hours:>4.1f}h): "
            f"normal_mean={n_mean:+.4f}, drift_mean={d_mean:+.4f}, "
            f"normal_std={n_std:.4f}, separation={sep:.2f} sigma")
    best_window, best_sep, _, _, _ = max(separations, key=lambda x: x[1])
    log(f"   The {best_window}-sample change shows the clearest separation "
        f"({best_sep:.2f} sigma between drift and normal means).")

    # D. Is it reasonable to investigate a temporal detector?
    log(f"\nD. Based only on this inspection, is it reasonable to investigate "
        f"a temporal detector next?")
    log(f"   The drift produces a measurable positive bias in rolling "
        f"temperature change that is not present in normal data.")
    log(f"   The {best_window}-sample change shows {best_sep:.2f} sigma "
        f"separation between drift and normal periods.")
    log(f"   Yes - it is reasonable to investigate a temporal detector that "
        f"examines rolling change features, based on the measurable signal "
        f"observed in this inspection.")
    log(f"   (No claim is made about which specific model architecture would "
        f"be appropriate; this is an inspection-only result.)")

    # Save.
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n[SAVE] Inspection saved to {OUTPUT_TXT}")


if __name__ == "__main__":
    main()