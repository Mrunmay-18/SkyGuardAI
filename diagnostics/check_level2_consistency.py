import sys
from pathlib import Path

import pandas as pd

# Allow imports from src/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.qc_rules import apply_qc_rules
from src.spatial_analysis import apply_spatial_analysis, _compute_station_baselines
from src.temporal_detector import apply_temporal_detector
from src.feature_engineering import build_features


TEST_FILE = ROOT / "data" / "test_injected_aws.csv"
NORMAL_FILE = ROOT / "data" / "normal_aws_data.csv"
PRED_FILE = ROOT / "data" / "isolation_forest_predictions.csv"


print("=" * 70)
print("CHECKING STEP 17 LEVEL-2 COUNT CONSISTENCY")
print("=" * 70)


# ---------------------------------------------------------
# 1. Load test data
# ---------------------------------------------------------
df = pd.read_csv(TEST_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

print(f"\nTest observations: {len(df)}")


# ---------------------------------------------------------
# 2. Temporal detector
# ---------------------------------------------------------
temporal = apply_temporal_detector(df.copy())

print(f"Temporal output rows: {len(temporal)}")

level2 = temporal["temporal_level2_flag"].fillna(0).astype(int)

print(f"Level-2 flagged rows: {level2.sum()}")

level2_candidates = temporal[
    (temporal["temporal_level2_flag"] == 1)
    & (temporal["temporal_level1_flag"] == 0)
].copy()

print(
    f"Level-2 AND Level-1==0 rows: "
    f"{len(level2_candidates)}"
)


# ---------------------------------------------------------
# 3. QC
# ---------------------------------------------------------
df_features = build_features(df.copy())
qc = apply_qc_rules(df_features.copy())
print(f"QC output rows: {len(qc)}")


# ---------------------------------------------------------
# 4. Spatial
# ---------------------------------------------------------
baselines = _compute_station_baselines(
    NORMAL_FILE,
    df["station_id"].unique()
)

metadata = pd.read_csv(
    ROOT / "data" / "station_metadata.csv"
)

spatial = apply_spatial_analysis(
    df.copy(),
    metadata,
    baselines=baselines
)

print(f"Spatial output rows: {len(spatial)}")


# ---------------------------------------------------------
# 5. Isolation Forest predictions
# ---------------------------------------------------------
pred = pd.read_csv(PRED_FILE)

print(f"IF prediction rows: {len(pred)}")

if "predicted_anomaly" not in pred.columns:
    raise ValueError(
        "Column 'predicted_anomaly' not found in IF predictions."
    )


# ---------------------------------------------------------
# 6. Reproduce the classifier-style joins
# ---------------------------------------------------------
base = df.copy()

# Keep only required temporal columns
temporal_cols = [
    "station_id",
    "timestamp",
    "temporal_level1_flag",
    "temporal_level2_flag",
    "temporal_predicted_anomaly",
]

temporal_small = temporal[temporal_cols].copy()

# QC
qc_cols = [
    "station_id",
    "timestamp",
    "qc_any_flag",
]

qc_small = qc[qc_cols].copy()

# Spatial
spatial_cols = [
    "station_id",
    "timestamp",
    "spatial_isolated_flag",
]

spatial_small = spatial[spatial_cols].copy()

# IF predictions
if_cols = [
    "station_id",
    "timestamp",
    "predicted_anomaly",
]

if_small = pred[if_cols].copy()


# Make timestamps consistent
for x in [
    temporal_small,
    qc_small,
    spatial_small,
    if_small,
]:
    x["timestamp"] = pd.to_datetime(x["timestamp"])


joined = base.merge(
    temporal_small,
    on=["station_id", "timestamp"],
    how="left",
)

joined = joined.merge(
    qc_small,
    on=["station_id", "timestamp"],
    how="left",
)

joined = joined.merge(
    spatial_small,
    on=["station_id", "timestamp"],
    how="left",
)

joined = joined.merge(
    if_small,
    on=["station_id", "timestamp"],
    how="left",
)


# Fill missing evidence exactly as binary zeros
for col in [
    "temporal_level1_flag",
    "temporal_level2_flag",
    "qc_any_flag",
    "spatial_isolated_flag",
    "predicted_anomaly",
]:
    joined[col] = joined[col].fillna(0).astype(int)


print(f"\nJoined rows: {len(joined)}")


# ---------------------------------------------------------
# 7. Count Level-2 after join
# ---------------------------------------------------------
joined_l2 = joined[
    (joined["temporal_level2_flag"] == 1)
    & (joined["temporal_level1_flag"] == 0)
].copy()

print(
    "\nLevel-2 + Level-1==0 AFTER classifier-style join: "
    f"{len(joined_l2)}"
)


# ---------------------------------------------------------
# 8. Supporting evidence combinations
# ---------------------------------------------------------
def combination(row):
    flags = []

    if row["predicted_anomaly"] == 1:
        flags.append("IF")

    if row["qc_any_flag"] == 1:
        flags.append("QC")

    if row["spatial_isolated_flag"] == 1:
        flags.append("SPATIAL")

    return " + ".join(flags) if flags else "NONE"


joined_l2["support_combination"] = joined_l2.apply(
    combination,
    axis=1,
)


print("\nEvidence combinations:")
print(
    joined_l2["support_combination"]
    .value_counts()
    .to_string()
)


# ---------------------------------------------------------
# 9. Current classifier rule
#    L2 + (IF OR QC OR Spatial)
# ---------------------------------------------------------
current_rule = joined_l2[
    (joined_l2["predicted_anomaly"] == 1)
    | (joined_l2["qc_any_flag"] == 1)
    | (joined_l2["spatial_isolated_flag"] == 1)
].copy()


print(
    "\nCurrent Calibration Drift rule:"
    "\nL2 + (IF OR QC OR Spatial)"
)

print(f"Rows: {len(current_rule)}")

print(
    f"Actual anomalies: "
    f"{current_rule['is_anomaly'].sum()}"
)

print(
    f"Normal rows: "
    f"{(current_rule['is_anomaly'] == 0).sum()}"
)


if len(current_rule) > 0:
    precision = (
        current_rule["is_anomaly"].sum()
        / len(current_rule)
    )
else:
    precision = 0.0

print(f"Precision: {precision:.4f}")


# ---------------------------------------------------------
# 10. Anomaly type distribution
# ---------------------------------------------------------
print("\nAnomaly types in current-rule rows:")

print(
    pd.crosstab(
        current_rule["anomaly_type"],
        current_rule["is_anomaly"],
    ).to_string()
)


# ---------------------------------------------------------
# 11. Final consistency summary
# ---------------------------------------------------------
print("\n" + "=" * 70)
print("CONSISTENCY SUMMARY")
print("=" * 70)

print(f"Temporal total rows:                  {len(temporal)}")
print(f"Temporal Level-2 rows:                {level2.sum()}")
print(f"Level-2 & Level-1==0 before join:     {len(level2_candidates)}")
print(f"Joined total rows:                    {len(joined)}")
print(f"Level-2 & Level-1==0 after join:      {len(joined_l2)}")
print(f"Current rule rows:                    {len(current_rule)}")

print("=" * 70)