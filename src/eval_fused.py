"""
Quick fused-evaluation script.
Loads all evidence sources, runs fuse_evidence(), evaluates against ground truth.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

from feature_engineering import build_features
from qc_rules import apply_qc_rules
from spatial_analysis import apply_spatial_analysis
from temporal_detector import apply_temporal_detector
from evidence_fusion import fuse_evidence


def main():
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])

    # Evidence sources
    f = build_features(obs)
    q = apply_qc_rules(f)

    m = pd.read_csv("data/station_metadata.csv")
    s = apply_spatial_analysis(obs, m)

    t = apply_temporal_detector(obs)

    ifd = pd.read_csv("data/isolation_forest_predictions.csv")
    ifd["timestamp"] = pd.to_datetime(ifd["timestamp"])
    ifd = ifd[["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]]

    # Merge all
    qc_cols = ["station_id", "timestamp"] + [c for c in q.columns if c.startswith("qc_")]
    sp_cols = ["station_id", "timestamp"] + [c for c in s.columns if c.startswith("spatial_")]
    tp_cols = ["station_id", "timestamp"] + [c for c in t.columns if c.startswith("temporal_")]

    j = obs.merge(ifd, on=["station_id", "timestamp"], how="left")
    j = j.merge(q[qc_cols], on=["station_id", "timestamp"], how="left")
    j = j.merge(s[sp_cols], on=["station_id", "timestamp"], how="left")
    j = j.merge(t[tp_cols], on=["station_id", "timestamp"], how="left")

    # Fuse
    fused = fuse_evidence(j)
    print("Fused output columns:")
    print(list(fused.columns))
    print()

    # Find alert column
    alert_col = None
    for cand in ["fused_any_flag", "fused_alert", "fusion_alert",
                 "is_alert", "alert", "final_alert", "fusion_decision"]:
        if cand in fused.columns:
            alert_col = cand
            break

    print("Alert column detected:", alert_col)
    print()

    if alert_col is None:
        print("No alert column found — inspect fused.head() manually.")
        print(fused.head(3).T)
        return

    y = fused["is_anomaly"].fillna(0).astype(int)
    p = fused[alert_col].fillna(0).astype(int)

    print("Rows total:        ", len(fused))
    print("Actual anomalies:  ", int(y.sum()))
    print("Fused alerts:      ", int(p.sum()))
    print()
    print("Precision:         ", round(precision_score(y, p, zero_division=0), 4))
    print("Recall:            ", round(recall_score(y, p, zero_division=0), 4))
    print("F1:                ", round(f1_score(y, p, zero_division=0), 4))
    print()
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(y, p, labels=[0, 1]))
    import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from feature_engineering import build_features
from qc_rules import apply_qc_rules
from spatial_analysis import apply_spatial_analysis
from temporal_detector import apply_temporal_detector
from evidence_fusion import fuse_evidence

obs = pd.read_csv("data/test_injected_aws.csv")
obs["timestamp"] = pd.to_datetime(obs["timestamp"])
f = build_features(obs)
q = apply_qc_rules(f)
m = pd.read_csv("data/station_metadata.csv")
s = apply_spatial_analysis(obs, m)
t = apply_temporal_detector(obs)
ifd = pd.read_csv("data/isolation_forest_predictions.csv")
ifd["timestamp"] = pd.to_datetime(ifd["timestamp"])
ifd = ifd[["station_id","timestamp","predicted_anomaly","anomaly_score"]]

j = obs.merge(ifd, on=["station_id","timestamp"], how="left")
j = j.merge(q[[c for c in q.columns if c.startswith("qc_") or c in ["station_id","timestamp"]]], on=["station_id","timestamp"], how="left")
j = j.merge(s[[c for c in s.columns if c.startswith("spatial_") or c in ["station_id","timestamp"]]], on=["station_id","timestamp"], how="left")
j = j.merge(t[[c for c in t.columns if c.startswith("temporal_") or c in ["station_id","timestamp"]]], on=["station_id","timestamp"], how="left")

fused = fuse_evidence(j)

# For rows where fused_any_flag == 1, which evidence sources fired?
fp_rows = fused[(fused["fused_any_flag"] == 1) & (fused["is_anomaly"] == 0)]
tp_rows = fused[(fused["fused_any_flag"] == 1) & (fused["is_anomaly"] == 1)]

def source_counts(df, label):
    print(f"\n--- {label} ({len(df)} rows) ---")
    for col in ["predicted_anomaly", "qc_any_flag", "temporal_predicted_anomaly",
                "spatial_any_flag", "spatial_isolated_flag", "spatial_common_event_flag",
                "temporal_level1_flag", "temporal_level2_flag"]:
        if col in df.columns:
            print(f"  {col:35s}: {int(df[col].fillna(0).sum())}")

source_counts(fp_rows, "FALSE POSITIVES")
source_counts(tp_rows, "TRUE POSITIVES")

# How many FP rows have ONLY spatial firing (and nothing else)?
if all(c in fp_rows.columns for c in ["predicted_anomaly","qc_any_flag","temporal_predicted_anomaly","spatial_any_flag"]):
    only_spatial = fp_rows[
        (fp_rows["spatial_any_flag"] == 1) &
        (fp_rows["predicted_anomaly"].fillna(0) == 0) &
        (fp_rows["qc_any_flag"] == 0) &
        (fp_rows["temporal_predicted_anomaly"].fillna(0) == 0)
    ]
    print(f"\nFPs where ONLY spatial fired: {len(only_spatial)} / {len(fp_rows)}")

    only_temporal = fp_rows[
        (fp_rows["temporal_predicted_anomaly"] == 1) &
        (fp_rows["predicted_anomaly"].fillna(0) == 0) &
        (fp_rows["qc_any_flag"] == 0) &
        (fp_rows["spatial_any_flag"] == 0)
    ]
    print(f"FPs where ONLY temporal fired: {len(only_temporal)} / {len(fp_rows)}")

    only_if = fp_rows[
        (fp_rows["predicted_anomaly"].fillna(0) == 1) &
        (fp_rows["qc_any_flag"] == 0) &
        (fp_rows["temporal_predicted_anomaly"] == 0) &
        (fp_rows["spatial_any_flag"] == 0)
    ]
    print(f"FPs where ONLY IF fired: {len(only_if)} / {len(fp_rows)}")


if __name__ == "__main__":
    main()