"""
src/feature_engineering.py
SkyGuard AI - Feature engineering for AWS anomaly detection.

Transforms raw AWS readings (temperature, pressure, humidity) into
ML-ready features. Works identically for:
  - data/normal_aws_data.csv        (no ground-truth labels)
  - data/test_injected_aws.csv      (with is_anomaly, anomaly_type,
                                     injected_parameter)

The ground-truth columns, if present, are PASSED THROUGH unchanged and
are NEVER included in FEATURE_COLUMNS. They are intended for downstream
evaluation only.

This module does NOT train any model and does NOT modify the input CSVs.
"""

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Column contracts
# ----------------------------------------------------------------------

# Columns that MUST be present in any input DataFrame passed to
# build_features(). If any are missing, a clear ValueError is raised.
REQUIRED_COLUMNS = [
    "station_id",
    "timestamp",
    "temperature",
    "pressure",
    "humidity",
]

# Ground-truth / label columns. These are OPTIONAL in the input. If they
# exist, they are kept in the returned DataFrame for later evaluation,
# but NEVER used as model features.
LABEL_COLUMNS = ["is_anomaly", "anomaly_type", "injected_parameter"]

# Final ordered list of model feature columns (raw + temporal + time).
# Downstream training / scoring code should select EXACTLY these columns
# when feeding data into an anomaly-detection model.
FEATURE_COLUMNS = [
    # raw measurements
    "temperature",
    "pressure",
    "humidity",
    # temporal first-difference features (per station)
    "d_temperature",
    "d_pressure",
    "d_humidity",
    # time / season features
    "hour",
    "hour_sin",
    "hour_cos",
    "day_of_year",
    "doy_sin",
    "doy_cos",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build ML-ready features from raw AWS readings.

    Steps:
      1. Validate REQUIRED_COLUMNS are present.
      2. Parse `timestamp` as datetime (errors coerced to NaT, then dropped).
      3. Stable sort by ["station_id", "timestamp"].
      4. Compute per-station first differences for temperature, pressure,
         humidity (first row of each station is NaN by design).
      5. Derive hour / day_of_year and their cyclic sine/cosine encodings.
      6. Keep optional label columns (is_anomaly, anomaly_type,
         injected_parameter) if they were present in the input.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with REQUIRED_COLUMNS (label columns optional).

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame. New columns added: d_temperature, d_pressure,
        d_humidity, hour, hour_sin, hour_cos, day_of_year, doy_sin,
        doy_cos. Original columns (including optional labels) preserved.
    """
    # --- 1. Validate required columns ---------------------------------
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Required: {REQUIRED_COLUMNS}."
        )

    # Work on a copy so the caller's DataFrame is never mutated and the
    # original CSV on disk is never touched.
    out = df.copy()

    # --- 2. Parse timestamp (coerce errors to NaT, then drop) ---------
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    n_before = len(out)
    out = out[out["timestamp"].notna()].copy()
    n_after = len(out)
    if n_after == 0:
        raise ValueError(
            "DataFrame is empty after dropping rows with invalid (NaT) "
            "timestamps. Cannot compute features."
        )
    if n_after < n_before:
        print(f"[feature_engineering] Dropped {n_before - n_after} row(s) "
              f"with invalid timestamps.")

    # --- 3. Stable sort by station then timestamp --------------------
    # Stable sort keeps the relative order of equal keys, which makes the
    # downstream first-difference deterministic.
    out = out.sort_values(["station_id", "timestamp"],
                           kind="stable").reset_index(drop=True)

    # --- 4. Per-station first differences (NEVER across stations) ------
    # groupby("station_id")[col].diff() computes the difference between
    # the current row and the PREVIOUS row OF THE SAME STATION. This
    # guarantees we never compute a difference across station boundaries.
    #
    # The first row of each station has no previous row, so its diff is
    # NaN BY DESIGN. We intentionally do NOT fill it with 0 (or any
    # value) because a fake "no change" signal would look like a
    # frozen-sensor anomaly to downstream models.
    for col, dcol in [
        ("temperature", "d_temperature"),
        ("pressure",    "d_pressure"),
        ("humidity",    "d_humidity"),
    ]:
        out[dcol] = out.groupby("station_id")[col].diff()

    # --- 5. Time / season features with cyclic encoding --------------
    # Raw hour (0..23) and day_of_year (1..365/366) are useful as-is for
    # tree-based models. The sine/cosine cyclic encodings let linear or
    # distance-based models understand that hour=23 and hour=0 are
    # adjacent (not 23 apart), and that day=365 and day=1 are adjacent.
    out["hour"] = out["timestamp"].dt.hour
    out["day_of_year"] = out["timestamp"].dt.dayofyear

    out["hour_sin"] = np.sin(2.0 * np.pi * out["hour"] / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * out["hour"] / 24.0)
    out["doy_sin"]  = np.sin(2.0 * np.pi * out["day_of_year"] / 365.0)
    out["doy_cos"]  = np.cos(2.0 * np.pi * out["day_of_year"] / 365.0)

    # --- 6. Optional label columns ----------------------------------
    # Optional label columns (is_anomaly, anomaly_type, injected_parameter)
    # are already preserved by the .copy() above. No extra action needed.
    # They are explicitly NOT in FEATURE_COLUMNS, so downstream ML code
    # won't accidentally use them as input features.

    return out


# ----------------------------------------------------------------------
# Demo / smoke test - only runs when executed directly.
# Loads both CSVs, builds features, prints shapes / columns / heads.
# Does NOT save anything to disk and does NOT train any model.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    NORMAL_CSV = "data/normal_aws_data.csv"
    INJECTED_CSV = "data/test_injected_aws.csv"

    print("=" * 70)
    print("SkyGuard AI - Feature engineering smoke test")
    print("=" * 70)

    for label, path in [("NORMAL  ", NORMAL_CSV), ("INJECTED", INJECTED_CSV)]:
        print(f"\n--- {label}  ({path}) ---")
        df_raw = pd.read_csv(path)
        print(f"raw shape     : {df_raw.shape}")
        print(f"raw columns   : {list(df_raw.columns)}")

        feats = build_features(df_raw)
        print(f"feats shape   : {feats.shape}")
        print(f"feats columns : {list(feats.columns)}")
        print("feats head(3):")
        print(feats.head(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("FEATURE_COLUMNS (downstream ML input):")
    for i, c in enumerate(FEATURE_COLUMNS, 1):
        print(f"  {i:2d}. {c}")
    print("=" * 70)