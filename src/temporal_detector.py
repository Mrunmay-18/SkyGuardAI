"""
src/temporal_detector.py
SkyGuard AI - STEP 16-F: Temporal Detector Experiment.

Station-wise, hour-conditioned, persistence-based temporal detector.
This is an EXPERIMENT to test whether temporal information can recover
anomalies missed by the Isolation Forest (specifically the 84
calibration_drift rows IF missed).

Two detection levels (exactly two — no Level 3):
  Level 1: Per-row anomaly (|z_N| > k_high for any window)
  Level 2: Persistent mild deviation (z_N > k_low for M consecutive
           observations, or z_N < -k_low for M consecutive)

Baselines are computed from data/normal_aws_data.csv ONLY. Parameters
(k_high=3.0, k_low=1.0, M=8) are fixed statistical conventions, NOT
tuned on test labels.

Does NOT modify any existing file. Uses pandas and numpy only.
"""

import os
import sys

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
NORMAL_DATA_PATH = "data/normal_aws_data.csv"
IF_PREDICTIONS_PATH = "data/isolation_forest_predictions.csv"

OUTPUT_DIR = "diagnostics"
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "temporal_detector_experiment.txt")

# Sibling src/ for potential future reuse (not needed now, but kept
# for consistency with the project structure).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


# ----------------------------------------------------------------------
# Fixed parameters (NOT tuned on test data)
# ----------------------------------------------------------------------
WINDOWS = [4, 8, 16]
K_HIGH = 3.0     # per-row 3-sigma threshold (statistical process control convention)
K_LOW = 1.0     # persistence threshold (mild sustained deviation)
M = 8            # consecutive samples = 2 hours at 15-min cadence
MIN_BIN_SAMPLES = 10  # minimum samples per (station, hour) bin; fallback to 3-hour block

# Required columns for detection (hard requirement — raises ValueError
# if any are missing, because temporal detection cannot proceed without them).
REQUIRED_COLUMNS = ["station_id", "timestamp", "temperature"]

# Columns required for evaluation (soft requirement — noted if missing,
# but detection proceeds; the demo's evaluation section will be limited).
EVALUATION_COLUMNS = ["is_anomaly", "anomaly_type"]


# ----------------------------------------------------------------------
# Feature computation
# ----------------------------------------------------------------------
def _compute_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute temp_change_4, temp_change_8, temp_change_16 and hour.

    Per station (groupby station_id), sorted by timestamp.
    First N rows per station have NaN — do NOT fill with 0.

    Returns a copy; the input is NOT mutated.
    """
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    # Sort per station to ensure correct diff() ordering.
    out = out.sort_values(["station_id", "timestamp"]).reset_index(drop=False)
    # Keep the original index in a column so we can restore it later.
    # "index" column holds the original row positions from `out`.

    for w in WINDOWS:
        out[f"temp_change_{w}"] = out.groupby("station_id")["temperature"].diff(w)

    out["hour"] = out["timestamp"].dt.hour
    return out


# ----------------------------------------------------------------------
# Baseline computation (from normal data ONLY)
# ----------------------------------------------------------------------
def _compute_baselines(normal_df: pd.DataFrame) -> dict:
    """
    Compute station-wise, hour-conditioned baselines from normal data.

    For each station S, hour h, window N:
        mu[S][h][N] = mean of temp_change_N at that (S, h)
        sd[S][h][N] = sample std (ddof=1)

    If a (S, h, N) bin has < MIN_BIN_SAMPLES, fall back to a 3-hour
    block (hours 0-2, 3-5, ..., 21-23).

    Returns a nested dict: baselines[S][h][N] = (mu, sd).
    Also includes baselines["__global__"][h][N] = (mu, sd) as a final
    fallback for stations missing from the training data.
    """
    feats = _compute_temporal_features(normal_df)

    baselines = {}

    # Per-station, per-hour baselines.
    for station_id, g in feats.groupby("station_id"):
        baselines[station_id] = {}
        for h in range(24):
            baselines[station_id][h] = {}
            for w in WINDOWS:
                col = f"temp_change_{w}"
                vals = g.loc[g["hour"] == h, col].dropna()

                # Fallback to 3-hour block if too few samples.
                if len(vals) < MIN_BIN_SAMPLES:
                    block_start = (h // 3) * 3
                    block_hours = list(range(block_start, block_start + 3))
                    vals = g.loc[g["hour"].isin(block_hours), col].dropna()

                if len(vals) >= 2:
                    mu = float(vals.mean())
                    sd = float(vals.std(ddof=1))
                    if np.isnan(sd) or sd == 0:
                        sd = 1e-6
                    baselines[station_id][h][w] = (mu, sd)
                else:
                    # Not enough data even with 3-hour fallback; use a
                    # placeholder that will trigger the global fallback.
                    baselines[station_id][h][w] = None

    # Global baselines (final fallback for stations missing from training).
    global_baselines = {}
    for h in range(24):
        global_baselines[h] = {}
        for w in WINDOWS:
            col = f"temp_change_{w}"
            vals = feats.loc[feats["hour"] == h, col].dropna()

            if len(vals) < MIN_BIN_SAMPLES:
                block_start = (h // 3) * 3
                block_hours = list(range(block_start, block_start + 3))
                vals = feats.loc[feats["hour"].isin(block_hours), col].dropna()

            if len(vals) >= 2:
                mu = float(vals.mean())
                sd = float(vals.std(ddof=1))
                if np.isnan(sd) or sd == 0:
                    sd = 1e-6
                global_baselines[h][w] = (mu, sd)
            else:
                global_baselines[h][w] = (0.0, 1e-6)

    baselines["__global__"] = global_baselines
    return baselines


def _get_baseline(baselines: dict, station_id: str, hour: int, window: int):
    """
    Returns (mu, sd, is_fallback) for the given (station, hour, window).

    Falls back to global baselines if the station is missing from the
    training data or the (S, h, N) bin had insufficient samples.
    """
    if (station_id in baselines
            and hour in baselines[station_id]
            and window in baselines[station_id][hour]
            and baselines[station_id][hour][window] is not None):
        mu, sd = baselines[station_id][hour][window]
        return mu, sd, False
    # Fall back to global.
    g = baselines.get("__global__", {})
    if hour in g and window in g[hour]:
        mu, sd = g[hour][window]
        return mu, sd, True
    return 0.0, 1e-6, True


# ----------------------------------------------------------------------
# Z-score computation
# ----------------------------------------------------------------------
def _compute_z_scores(df: pd.DataFrame, baselines: dict) -> pd.DataFrame:
    """
    Compute temporal_z_4, temporal_z_8, temporal_z_16.

    z_N = (temp_change_N - mu[S][h][N]) / sd[S][h][N]

    Rows with NaN temp_change_N (first N rows per station) get NaN z_N.
    """
    out = df.copy()
    for w in WINDOWS:
        z_col = f"temporal_z_{w}"
        change_col = f"temp_change_{w}"
        z_vals = np.full(len(out), np.nan)
        changes = out[change_col].to_numpy()
        hours = out["hour"].to_numpy()
        stations = out["station_id"].to_numpy()

        for i in range(len(out)):
            if np.isnan(changes[i]):
                continue
            mu, sd, _ = _get_baseline(
                baselines, stations[i], int(hours[i]), w
            )
            z_vals[i] = (changes[i] - mu) / sd

        out[z_col] = z_vals
    return out


# ----------------------------------------------------------------------
# Level 1: Per-row anomaly
# ----------------------------------------------------------------------
def _detect_level1(df: pd.DataFrame) -> tuple:
    """
    Level 1: flag if |z_N| > K_HIGH for ANY window.

    Returns (level1_flag_array, level1_reason_list).
    """
    n = len(df)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    z_cols = [f"temporal_z_{w}" for w in WINDOWS]
    z_data = {w: df[f"temporal_z_{w}"].to_numpy() for w in WINDOWS}

    for i in range(n):
        parts = []
        for w in WINDOWS:
            z = z_data[w][i]
            if np.isnan(z):
                continue
            if abs(z) > K_HIGH:
                parts.append(f"|z_{w}|={abs(z):.1f}")
        if parts:
            flags[i] = 1
            reasons[i] = "level1: " + "; ".join(parts)

    return flags, reasons


# ----------------------------------------------------------------------
# Level 2: Persistent mild deviation
# ----------------------------------------------------------------------
def _detect_level2_per_station(station_df: pd.DataFrame) -> tuple:
    """
    Level 2 for a single station: check for sustained z_N > K_LOW
    (or z_N < -K_LOW) for M consecutive observations.

    NaN z_N BREAKS consecutive runs — do NOT forward-fill or
    back-fill. A "run of M consecutive z > K_LOW" means M ADJACENT
    rows in the same station with valid (non-NaN) z_N, all
    satisfying the threshold condition.

    The reason string reports the current run_length at each
    flagged row (e.g. 8, 9, 10, ...), not always "M".

    Returns (level2_flag_array, level2_reason_list) aligned to
    station_df's index.
    """
    n = len(station_df)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    for w in WINDOWS:
        z_col = f"temporal_z_{w}"
        z = station_df[z_col]

        # --- Positive sustained deviation: z > K_LOW for M consecutive ---
        # NaN breaks runs: cond is False where z is NaN or z <= K_LOW.
        cond_pos = (z > K_LOW)
        cond_pos = cond_pos.where(z.notna(), False)  # NaN breaks runs

        if cond_pos.any():
            # run_id increments at each False (break in the run).
            run_id_pos = (~cond_pos).cumsum()
            # run_length: how many consecutive True values ending at
            # this position (within the current run).
            run_length_pos = cond_pos.groupby(run_id_pos).cumcount() + 1
            # Flag only rows where the running count has reached M
            # or more. Rows before the Mth consecutive observation
            # (run_length 1..M-1) are NOT flagged.
            flagged_pos = (run_length_pos >= M) & cond_pos

            for idx in station_df.index[flagged_pos.to_numpy()]:
                pos_in_station = station_df.index.get_loc(idx)
                actual_run = int(run_length_pos.iloc[pos_in_station])
                if flags[pos_in_station] == 0:
                    flags[pos_in_station] = 1
                    reasons[pos_in_station] = (
                        f"level2: z_{w} sustained >{K_LOW} for "
                        f"{actual_run} consecutive samples"
                    )
                else:
                    # Already flagged by another window — append.
                    reasons[pos_in_station] += (
                        f"; level2: z_{w} sustained >{K_LOW} for "
                        f"{actual_run} consecutive samples"
                    )

        # --- Negative sustained deviation: z < -K_LOW for M consecutive ---
        cond_neg = (z < -K_LOW)
        cond_neg = cond_neg.where(z.notna(), False)  # NaN breaks runs

        if cond_neg.any():
            run_id_neg = (~cond_neg).cumsum()
            run_length_neg = cond_neg.groupby(run_id_neg).cumcount() + 1
            # Flag only rows where the running count has reached M
            # or more. Rows before the Mth consecutive observation
            # (run_length 1..M-1) are NOT flagged.
            flagged_neg = (run_length_neg >= M) & cond_neg

            for idx in station_df.index[flagged_neg.to_numpy()]:
                pos_in_station = station_df.index.get_loc(idx)
                actual_run = int(run_length_neg.iloc[pos_in_station])
                if flags[pos_in_station] == 0:
                    flags[pos_in_station] = 1
                    reasons[pos_in_station] = (
                        f"level2: z_{w} sustained <-{K_LOW} for "
                        f"{actual_run} consecutive samples"
                    )
                else:
                    reasons[pos_in_station] += (
                        f"; level2: z_{w} sustained <-{K_LOW} for "
                        f"{actual_run} consecutive samples"
                    )

    return flags, reasons


def _detect_level2(df: pd.DataFrame) -> tuple:
    """
    Level 2 dispatch: process per station, preserve index alignment.

    IMPORTANT: After groupby("station_id"), we assign group-level
    results back using df.loc[group.index, ...] to preserve the
    original DataFrame index. Do NOT reset or reorder the index.

    Returns (level2_flag_array, level2_reason_list) aligned to df's
    index.
    """
    n = len(df)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    # Map df's index positions to array positions.
    index_to_pos = {idx: pos for pos, idx in enumerate(df.index)}

    for _station_id, group in df.groupby("station_id"):
        # Sort by timestamp within the station to ensure consecutive
        # rows are actually consecutive in time.
        group = group.sort_values("timestamp")

        l2_flags, l2_reasons = _detect_level2_per_station(group)

        # Assign back using the group's original index labels.
        for i, idx in enumerate(group.index):
            pos = index_to_pos[idx]
            flags[pos] = l2_flags[i]
            reasons[pos] = l2_reasons[i]

    return flags, reasons


# ----------------------------------------------------------------------
# Main detection function
# ----------------------------------------------------------------------
def apply_temporal_detector(df: pd.DataFrame,
                            baselines: dict | None = None) -> pd.DataFrame:
    """
    Apply the temporal detector to a DataFrame of observations.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: station_id, timestamp, temperature.
    baselines : dict | None
        Pre-computed baselines from _compute_baselines(). If None,
        loads from data/normal_aws_data.csv.

    Returns
    -------
    pd.DataFrame
        Copy of df with ADDED columns:
          temp_change_4, temp_change_8, temp_change_16,
          temporal_z_4, temporal_z_8, temporal_z_16,
          temporal_level1_flag, temporal_level2_flag,
          temporal_predicted_anomaly, temporal_reason.
        The input is NOT mutated.
    """
    # --- Graceful validation of required columns ---
    # Core detection columns: hard requirement. Raise ValueError so
    # the caller knows the input is incompatible.
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_required:
        raise ValueError(
            f"Missing required columns for temporal detection: "
            f"{missing_required}. Required: {REQUIRED_COLUMNS}."
        )
    # Evaluation columns: soft requirement. Note if missing but do
    # NOT raise — the detector can still run; the evaluation section
    # of the demo will simply be limited.
    missing_eval = [c for c in EVALUATION_COLUMNS if c not in df.columns]
    if missing_eval:
        print(f"[temporal_detector] NOTE: evaluation columns missing "
              f"(evaluation will be limited): {missing_eval}")

    if baselines is None:
        normal_df = pd.read_csv(NORMAL_DATA_PATH)
        baselines = _compute_baselines(normal_df)

    # Compute features (sorts per station, adds hour + temp_change_*).
    # NOTE: _compute_temporal_features() sorts by (station_id,
    # timestamp) for chronological detection and preserves the original
    # row positions in an "index" column (via reset_index(drop=False)).
    # We restore the original input order at the end of this function.
    out = _compute_temporal_features(df)

    # Compute z-scores using hour-conditioned baselines.
    out = _compute_z_scores(out, baselines)

    # Level 1: per-row anomaly.
    l1_flags, l1_reasons = _detect_level1(out)
    out["temporal_level1_flag"] = l1_flags

    # Level 2: persistent mild deviation (per station, index-aligned).
    l2_flags, l2_reasons = _detect_level2(out)
    out["temporal_level2_flag"] = l2_flags

    # OR of Level 1 and Level 2.
    out["temporal_predicted_anomaly"] = (
        (out["temporal_level1_flag"] == 1) | (out["temporal_level2_flag"] == 1)
    ).astype(int)

    # Build combined reason string.
    combined_reasons = []
    for i in range(len(out)):
        l1 = l1_reasons[i]
        l2 = l2_reasons[i]
        parts = []
        if l1:
            parts.append(l1)
        else:
            parts.append("level1: none")
        if l2:
            parts.append(l2)
        else:
            parts.append("level2: none")
        combined_reasons.append("; ".join(parts))
    out["temporal_reason"] = combined_reasons

    # --- Restore original input row order ---
    # _compute_temporal_features() sorted by (station_id, timestamp)
    # for chronological station-wise detection. The "index" column
    # (from reset_index(drop=False)) holds the original row positions.
    # Sort by it now so the returned DataFrame is aligned 1:1 with the
    # input rows, regardless of the internal chronological reordering.
    # This does NOT change any detection results — it only reorders the
    # output rows to match the input.
    if "index" in out.columns:
        out = out.sort_values("index").reset_index(drop=True)
        out = out.drop(columns=["index"])

    return out


# ----------------------------------------------------------------------
# Demo / evaluation
# ----------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_lines = []

    def log(msg=""):
        print(msg)
        output_lines.append(msg)

    log("=" * 70)
    log("SkyGuard AI - STEP 16-F: Temporal Detector Experiment")
    log("=" * 70)

    # 1. Parameters used.
    log(f"\n--- Parameters (fixed, NOT tuned on test data) ---")
    log(f"  Windows:  {WINDOWS}")
    log(f"  k_high:   {K_HIGH}  (per-row 3-sigma threshold)")
    log(f"  k_low:    {K_LOW}  (persistence threshold)")
    log(f"  M:        {M}  consecutive samples (2 hours)")
    log(f"  Min bin samples: {MIN_BIN_SAMPLES} (fallback to 3-hour block)")

    # Load normal data and compute baselines.
    normal_df = pd.read_csv(NORMAL_DATA_PATH)
    baselines = _compute_baselines(normal_df)
    log(f"\n  Baselines computed from: {NORMAL_DATA_PATH}")

    # 2. Baseline summary.
    log(f"\n--- Baseline Summary ---")
    normal_feats = _compute_temporal_features(normal_df)
    for sid in sorted(normal_feats["station_id"].unique()):
        g = normal_feats[normal_feats["station_id"] == sid]
        log(f"\n  Station {sid}:")
        for w in WINDOWS:
            col = f"temp_change_{w}"
            vals = g[col].dropna()
            log(f"    {col} (global): mean={vals.mean():.4f}, "
                f"std={vals.std(ddof=1):.4f}")

        # Hour-conditioned std range for 16-sample change.
        col16 = "temp_change_16"
        hour_stds = []
        hour_means = []
        for h in range(24):
            hvals = g.loc[g["hour"] == h, col16].dropna()
            if len(hvals) >= 2:
                hour_stds.append(float(hvals.std(ddof=1)))
                hour_means.append(float(hvals.mean()))
        if hour_stds:
            log(f"    Hour-conditioned temp_change_16 std: "
                f"min={min(hour_stds):.4f}, "
                f"median={np.median(hour_stds):.4f}, "
                f"max={max(hour_stds):.4f}")
            log(f"    Hour-conditioned temp_change_16 mean: "
                f"min={min(hour_means):.4f}, "
                f"median={np.median(hour_means):.4f}, "
                f"max={max(hour_means):.4f}")

    # Load test data and run detector.
    test_df = pd.read_csv("data/test_injected_aws.csv")
    result = apply_temporal_detector(test_df, baselines=baselines)

    # 3. Aggregate results.
    log(f"\n--- Aggregate Results ---")
    log(f"  Total rows: {len(result)}")

    y_true = result["is_anomaly"].fillna(0).astype(int).to_numpy()
    y_pred = result["temporal_predicted_anomaly"].to_numpy()
    y_l1 = result["temporal_level1_flag"].to_numpy()
    y_l2 = result["temporal_level2_flag"].to_numpy()

    def _metrics(y_t, y_p):
        tp = int(((y_t == 1) & (y_p == 1)).sum())
        fp = int(((y_t == 0) & (y_p == 1)).sum())
        fn = int(((y_t == 1) & (y_p == 0)).sum())
        tn = int(((y_t == 0) & (y_p == 0)).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        return tp, fp, fn, tn, prec, rec, f1

    tp1, fp1, fn1, tn1, p1, r1, f1_1 = _metrics(y_true, y_l1)
    tp2, fp2, fn2, tn2, p2, r2, f1_2 = _metrics(y_true, y_l1 | y_l2)

    log(f"\n  {'Metric':<12s}  {'Level 1 only':>14s}  {'Level 1+2':>14s}")
    log(f"  {'-'*44}")
    log(f"  {'TP':<12s}  {tp1:>14d}  {tp2:>14d}")
    log(f"  {'FP':<12s}  {fp1:>14d}  {fp2:>14d}")
    log(f"  {'FN':<12s}  {fn1:>14d}  {fn2:>14d}")
    log(f"  {'TN':<12s}  {tn1:>14d}  {tn2:>14d}")
    log(f"  {'Precision':<12s}  {p1:>14.4f}  {p2:>14.4f}")
    log(f"  {'Recall':<12s}  {r1:>14.4f}  {r2:>14.4f}")
    log(f"  {'F1':<12s}  {f1_1:>14.4f}  {f1_2:>14.4f}")

    # 4. Per-anomaly-type detection table.
    log(f"\n--- Per-Anomaly-Type Detection ---")
    header = (f"  {'anomaly_type':<30s}  {'total':>6s}  "
              f"{'L1_det':>7s}  {'L2_det':>7s}  {'total_det':>9s}  "
              f"{'rate':>7s}")
    log(header)
    log("  " + "-" * (len(header) - 2))
    for atype, g in result.groupby("anomaly_type"):
        n_total = len(g)
        n_l1 = int(g["temporal_level1_flag"].sum())
        n_l2 = int(g["temporal_level2_flag"].sum())
        n_det = int(g["temporal_predicted_anomaly"].sum())
        rate = n_det / n_total if n_total > 0 else 0.0
        log(f"  {str(atype):<30s}  {n_total:>6d}  {n_l1:>7d}  "
            f"{n_l2:>7d}  {n_det:>9d}  {rate:>6.1%}")

    # 5. IF false-negative recovery.
    log(f"\n--- IF False-Negative Recovery ---")
    if os.path.exists(IF_PREDICTIONS_PATH):
        if_df = pd.read_csv(IF_PREDICTIONS_PATH)
        if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
        if_fn = if_df[
            (if_df["is_anomaly"] == 1) & (if_df["predicted_anomaly"] == 0)
        ].copy()

        # Join with temporal detector output.
        result_joined = result.merge(
            if_fn[["station_id", "timestamp", "anomaly_type"]].rename(
                columns={"anomaly_type": "if_fn_anomaly_type"}
            ),
            on=["station_id", "timestamp"],
            how="inner",
        )
        # result_joined now contains only IF false negatives that also
        # appear in the temporal detector output.

        log(f"  Total IF false negatives: {len(if_fn)}")
        log(f"  Matched in temporal output: {len(result_joined)}")
        log()

        header2 = (f"  {'anomaly_type':<30s}  {'IF_missed':>10s}  "
                   f"{'temporal_recovered':>19s}  {'recovery_rate':>14s}")
        log(header2)
        log("  " + "-" * (len(header2) - 2))
        for atype, g in if_fn.groupby("anomaly_type"):
            n_missed = len(g)
            # Find these rows in the temporal output.
            g_keys = g[["station_id", "timestamp"]].merge(
                result[["station_id", "timestamp", "temporal_predicted_anomaly"]],
                on=["station_id", "timestamp"],
                how="left",
            )
            n_recovered = int(g_keys["temporal_predicted_anomaly"].fillna(0).sum())
            rate = n_recovered / n_missed if n_missed > 0 else 0.0
            log(f"  {str(atype):<30s}  {n_missed:>10d}  "
                f"{n_recovered:>19d}  {rate:>13.1%}")

        # Explicitly report calibration_drift and frozen_sensor.
        cd = if_fn[if_fn["anomaly_type"] == "calibration_drift"]
        cd_keys = cd[["station_id", "timestamp"]].merge(
            result[["station_id", "timestamp", "temporal_predicted_anomaly"]],
            on=["station_id", "timestamp"],
            how="left",
        )
        cd_recovered = int(cd_keys["temporal_predicted_anomaly"].fillna(0).sum())

        fs = if_fn[if_fn["anomaly_type"] == "frozen_sensor"]
        fs_keys = fs[["station_id", "timestamp"]].merge(
            result[["station_id", "timestamp", "temporal_predicted_anomaly"]],
            on=["station_id", "timestamp"],
            how="left",
        )
        fs_recovered = int(fs_keys["temporal_predicted_anomaly"].fillna(0).sum())

        log(f"\n  Explicit:")
        log(f"    calibration_drift: {cd_recovered} / {len(cd)} recovered")
        log(f"    frozen_sensor:     {fs_recovered} / {len(fs)} recovered")
    else:
        log(f"  [SKIP] IF predictions not found at {IF_PREDICTIONS_PATH}")

    # 6. False-alarm rates.
    log(f"\n--- False-Alarm Rates ---")
    for atype in ["normal", "normal_weather_event"]:
        sub = result[result["anomaly_type"] == atype]
        n_total = len(sub)
        n_flagged = int(sub["temporal_predicted_anomaly"].sum())
        rate = n_flagged / n_total if n_total > 0 else 0.0
        log(f"  {atype:<25s}  total={n_total:>6d}  "
            f"flagged={n_flagged:>6d}  false_alarm_rate={rate:.2%}")

    # 7. Example rows.
    log(f"\n--- Example Rows ---")

    # 5 recovered drift rows.
    drift = result[result["anomaly_type"] == "calibration_drift"]
    recovered_drift = drift[drift["temporal_predicted_anomaly"] == 1].head(5)
    log(f"\n  5 recovered calibration_drift rows:")
    if recovered_drift.empty:
        log("    (none)")
    else:
        cols = ["timestamp", "station_id", "temp_change_16",
                "temporal_z_16", "temporal_reason"]
        for line in recovered_drift[cols].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            log("    " + line)

    # 5 still-missed drift rows.
    missed_drift = drift[drift["temporal_predicted_anomaly"] == 0].head(5)
    log(f"\n  5 still-missed calibration_drift rows:")
    if missed_drift.empty:
        log("    (none — all drift rows recovered)")
    else:
        cols = ["timestamp", "station_id", "temp_change_16",
                "temporal_z_16", "temporal_reason"]
        for line in missed_drift[cols].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            log("    " + line)

    # 5 false-alarm rows on normal_weather_event.
    we = result[
        (result["anomaly_type"] == "normal_weather_event")
        & (result["temporal_predicted_anomaly"] == 1)
    ].head(5)
    log(f"\n  5 false-alarm rows on normal_weather_event:")
    if we.empty:
        log("    (none)")
    else:
        cols = ["timestamp", "station_id", "temp_change_16",
                "temporal_z_16", "temporal_reason"]
        for line in we[cols].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            log("    " + line)

    # 5 false-alarm rows on normal.
    norm = result[
        (result["anomaly_type"] == "normal")
        & (result["temporal_predicted_anomaly"] == 1)
    ].head(5)
    log(f"\n  5 false-alarm rows on normal:")
    if norm.empty:
        log("    (none)")
    else:
        cols = ["timestamp", "station_id", "temp_change_16",
                "temporal_z_16", "temporal_reason"]
        for line in norm[cols].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            log("    " + line)

    # 8. Conclusion (factual only).
    log(f"\n{'='*70}")
    log("CONCLUSION (factual — no editorializing)")
    log(f"{'='*70}")

    log(f"\nA. How many of the 84 IF-missed calibration-drift rows did "
        f"the temporal detector recover?")
    log(f"   {cd_recovered} / {len(cd)}")

    log(f"\nB. How many of the 16 IF-missed frozen-sensor rows did "
        f"the temporal detector recover?")
    log(f"   {fs_recovered} / {len(fs)}")

    we_sub = result[result["anomaly_type"] == "normal_weather_event"]
    we_total = len(we_sub)
    we_flagged = int(we_sub["temporal_predicted_anomaly"].sum())
    we_rate = we_flagged / we_total if we_total > 0 else 0.0
    log(f"\nC. What is the false-alarm rate on normal_weather_event?")
    log(f"   {we_flagged} / {we_total} = {we_rate:.2%}")

    norm_sub = result[result["anomaly_type"] == "normal"]
    norm_total = len(norm_sub)
    norm_flagged = int(norm_sub["temporal_predicted_anomaly"].sum())
    norm_rate = norm_flagged / norm_total if norm_total > 0 else 0.0
    log(f"\nD. What is the false-alarm rate on normal?")
    log(f"   {norm_flagged} / {norm_total} = {norm_rate:.2%}")

    # Save report.
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n[SAVE] Report saved to {OUTPUT_TXT}")