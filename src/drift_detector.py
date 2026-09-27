"""
src/drift_detector.py
SkyGuard AI — Drift Detector (Phase 2 addition).

Detects slow, cumulative calibration drift in AWS sensors using a
rolling-baseline comparison per station and per parameter.

This is a SIXTH independent evidence source. It does not replace
Isolation Forest, QC rules, spatial, or temporal detection — it
complements them.

Conceptual distinction:
  - Sudden sensor/power collapse (all-zero, NaN) -> NOT drift
  - Gradual sustained shift over many readings   -> possible drift

Does NOT modify any existing file.
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
class DriftConfig:
    """
    All thresholds are PROTOTYPE HEURISTICS for demonstration.
    They are NOT scientifically validated standards.
    """
    BASELINE_WINDOW_ROWS: int = 672
    RECENT_WINDOW_ROWS: int = 24
    Z_THRESHOLD: float = 2.0
    MIN_CONSECUTIVE_ROWS: int = 12
    MIN_TEMP_DRIFT_C: float = 1.0
    MIN_PRESSURE_DRIFT_HPA: float = 5.0
    MIN_HUMIDITY_DRIFT_PCT: float = 5.0


# ----------------------------------------------------------------------
# Parameter validity checks (prevents collapse being called drift)
# ----------------------------------------------------------------------
# For each parameter, define what is physically valid.
# Values outside this range in the recent window invalidate the window
# as a drift candidate (that's a fault, not drift).
PARAM_VALID_RANGE = {
    "temperature": (-90.0, 60.0),    # °C — physically possible on Earth
    "pressure":    (300.0, 1100.0),  # hPa — sea-level to high-altitude
    "humidity":    (0.0, 100.0),     # % — physically bounded
}


def _window_is_valid_for_drift(values: np.ndarray, param: str) -> bool:
    """
    Return True if the recent window contains values consistent with
    gradual drift (not sensor collapse / power failure).

    Rejects windows with:
      - any NaN
      - any value outside the parameter's physical range
    """
    if np.isnan(values).any():
        return False
    lo, hi = PARAM_VALID_RANGE[param]
    if (values < lo).any() or (values > hi).any():
        return False
    return True


# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
def _compute_parameter_drift(
    series: pd.Series,
    param_name: str,
    baseline_window: int,
    recent_window: int,
    z_threshold: float,
    min_consecutive: int,
    min_physical_drift: float,
) -> tuple:
    """
    Compute drift flags for a single parameter of a single station.

    Uses BOTH:
      - recent mean vs baseline mean shift (z-score)
      - linear regression slope over the recent window
      - persistence over min_consecutive rows

    Returns (drift_flag array, drift_reason array).
    """
    n = len(series)
    drift_flag = np.zeros(n, dtype=int)
    drift_reason = np.array([""] * n, dtype=object)

    if n < baseline_window + recent_window + min_consecutive:
        return drift_flag, drift_reason

    values = series.to_numpy(dtype=float)

    # Track consecutive drift-candidate rows to enforce persistence.
    consecutive = 0

    for i in range(baseline_window + recent_window, n):
        b_start = i - baseline_window - recent_window
        b_end = i - recent_window
        baseline = values[b_start:b_end]
        baseline = baseline[~np.isnan(baseline)]
        if len(baseline) < baseline_window // 2:
            consecutive = 0
            continue

        b_mean = float(np.mean(baseline))
        b_std = float(np.std(baseline))
        if b_std < 1e-6:
            consecutive = 0
            continue

        recent = values[i - recent_window:i]

        # Reject collapse / invalid windows.
        if not _window_is_valid_for_drift(recent, param_name):
            consecutive = 0
            continue

        r_mean = float(np.mean(recent))
        mean_shift = r_mean - b_mean
        deviation_z = abs(mean_shift) / b_std
        physical_drift = abs(mean_shift)

        # Slope over the recent window (x = 0, 1, 2, ...).
        x = np.arange(len(recent), dtype=float)
        try:
            slope = float(np.polyfit(x, recent, 1)[0])
        except Exception:
            slope = 0.0

        # Direction consistency: slope must agree with mean shift.
        direction = "up" if mean_shift > 0 else "down"
        slope_agrees = (
            (slope > 0 and mean_shift > 0) or (slope < 0 and mean_shift < 0)
        )

        # Both conditions required for drift.
        is_candidate = (
            deviation_z > z_threshold
            and physical_drift > min_physical_drift
            and slope_agrees
        )

        if is_candidate:
            consecutive += 1
        else:
            consecutive = 0

        if is_candidate and consecutive >= min_consecutive:
            drift_flag[i] = 1
            drift_reason[i] = (
                f"drift {direction}: recent mean {r_mean:.2f} vs "
                f"baseline {b_mean:.2f} (Δ={mean_shift:+.2f}, "
                f"z={deviation_z:.1f}, slope={slope:+.4f}, "
                f"persist={consecutive})"
            )

    return drift_flag, drift_reason


def compute_drift(df: pd.DataFrame, config: DriftConfig | None = None) -> pd.DataFrame:
    """
    Compute drift flags per (station_id, timestamp) row.

    Input: raw AWS observations with columns
        station_id, timestamp, temperature, pressure, humidity.

    Output DataFrame with columns:
        station_id, timestamp,
        drift_temperature_flag, drift_pressure_flag, drift_humidity_flag,
        drift_any_flag, drift_reason
    """
    if config is None:
        config = DriftConfig()

    required = ["station_id", "timestamp", "temperature", "pressure", "humidity"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    param_map = {
        "temperature": ("drift_temperature_flag", config.MIN_TEMP_DRIFT_C),
        "pressure":    ("drift_pressure_flag",    config.MIN_PRESSURE_DRIFT_HPA),
        "humidity":    ("drift_humidity_flag",    config.MIN_HUMIDITY_DRIFT_PCT),
    }

    n = len(work)
    out_flags = {flag_col: np.zeros(n, dtype=int) for _, (flag_col, _) in param_map.items()}
    out_reasons = {flag_col: np.array([""] * n, dtype=object) for _, (flag_col, _) in param_map.items()}

    for sid, idx in work.groupby("station_id").groups.items():
        idx = np.array(sorted(idx))
        for param, (flag_col, min_drift) in param_map.items():
            series = work.loc[idx, param]
            flags, reasons = _compute_parameter_drift(
                series=series.reset_index(drop=True),
                param_name=param,
                baseline_window=config.BASELINE_WINDOW_ROWS,
                recent_window=config.RECENT_WINDOW_ROWS,
                z_threshold=config.Z_THRESHOLD,
                min_consecutive=config.MIN_CONSECUTIVE_ROWS,
                min_physical_drift=min_drift,
            )
            out_flags[flag_col][idx] = flags
            out_reasons[flag_col][idx] = reasons

    result = work[["station_id", "timestamp"]].copy()
    for flag_col in out_flags:
        result[flag_col] = out_flags[flag_col]
    result["drift_any_flag"] = (
        (result["drift_temperature_flag"] == 1)
        | (result["drift_pressure_flag"] == 1)
        | (result["drift_humidity_flag"] == 1)
    ).astype(int)

    reasons = []
    for i in range(len(result)):
        parts = []
        for flag_col in out_reasons:
            if result.iloc[i][flag_col] == 1:
                parts.append(out_reasons[flag_col][i])
        reasons.append(" | ".join(parts))
    result["drift_reason"] = reasons

    return result


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("SkyGuard AI - Drift Detector (standalone demo)")
    print("=" * 70)

    path = "data/test_injected_aws.csv"
    if not os.path.exists(path):
        print(f"[ERROR] {path} not found")
        sys.exit(1)

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")

    result = compute_drift(df)

    n_drift = int(result["drift_any_flag"].sum())
    print(f"\nTotal drift flags: {n_drift}")
    print(f"  temperature drift: {int(result['drift_temperature_flag'].sum())}")
    print(f"  pressure drift:    {int(result['drift_pressure_flag'].sum())}")
    print(f"  humidity drift:    {int(result['drift_humidity_flag'].sum())}")

    if "anomaly_type" in df.columns:
        # Align timestamp dtypes before merge.
        df_copy = df.copy()
        df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"], errors="coerce")
        merged = df_copy.merge(
            result[["station_id", "timestamp", "drift_any_flag"]],
            on=["station_id", "timestamp"], how="left"
        )
        n_injected = int((merged["anomaly_type"] == "calibration_drift").sum())
        n_detected = int(
            ((merged["anomaly_type"] == "calibration_drift") & (merged["drift_any_flag"] == 1)).sum()
        )
        print(f"\nInjected calibration_drift rows: {n_injected}")
        print(f"  Drift detector caught:        {n_detected}")
        if n_injected > 0:
            print(f"  Detection rate:               {n_detected / n_injected:.1%}")

    print("\nFirst 3 rows with drift flag:")
    sample = result[result["drift_any_flag"] == 1].head(3)
    if sample.empty:
        print("  (none)")
    else:
        for _, row in sample.iterrows():
            print(f"  {row['station_id']} @ {row['timestamp']}: {row['drift_reason']}")