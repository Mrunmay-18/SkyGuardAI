"""
evaluation/evaluate.py
SkyGuard AI - STEP 13: Read-only evaluation harness.

Reads a detector's predictions CSV (with ground-truth labels carried
through) and computes aggregate + per-anomaly-type metrics, with special
attention to whether genuine weather events (normal_weather_event) are
being incorrectly flagged as sensor faults.

This tool is READ-ONLY. It does NOT train, fit, predict, or modify any
model. It does NOT alter the prediction CSV. Ground-truth labels are
used ONLY for evaluation, never as model input.

Usage:
    python evaluation/evaluate.py \\
        --predictions data/isolation_forest_predictions.csv \\
        [--labels data/test_injected_aws.csv]

Defaults allow running with no arguments:
    python evaluation/evaluate.py
"""

import argparse
import os

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEFAULT_PREDICTIONS = "data/fused_predictions.csv"
DEFAULT_LABELS = "data/test_injected_aws.csv"

RESULTS_DIR = "results"
METRICS_CSV = os.path.join(RESULTS_DIR, "evaluation_metrics.csv")
SUMMARY_TXT = os.path.join(RESULTS_DIR, "evaluation_summary.txt")

# Columns used to join labels onto predictions if labels are missing.
JOIN_KEYS = ["station_id", "timestamp"]

# Label columns that may be carried in the predictions CSV.
LABEL_COLUMNS = ["is_anomaly", "anomaly_type", "injected_parameter"]

# Small-sample caveat (appended verbatim per the spec).
SMALL_SAMPLE_SUFFIX = " (n < 5; interpret cautiously)"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _safe_div(num: float, den: float) -> float:
    """Division that returns 0.0 when denominator is 0 (zero_division=0)."""
    return float(num) / float(den) if den > 0 else 0.0


def _small_sample_caveat(n: int) -> str:
    """Return the small-sample suffix if n < 5, else empty string."""
    return SMALL_SAMPLE_SUFFIX if n < 5 else ""


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
def load_predictions(pred_path: str,
                     labels_path: str = None) -> pd.DataFrame:
    """
    Load the predictions CSV. If is_anomaly / anomaly_type are missing,
    join them from the labels CSV on (station_id, timestamp).

    Does NOT double-join: only label columns absent from the predictions
    CSV are merged in.
    """
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Predictions CSV not found: {pred_path}")

    df = pd.read_csv(pred_path)
    # Prefer fused_any_flag if present — this is what the system actually outputs.
    if "fused_any_flag" in df.columns:
        df["predicted_anomaly"] = df["fused_any_flag"].astype(int)

    # Bare minimum required columns (the rest can be joined or evaluated
    # conditionally).
    required_min = ["timestamp", "station_id"]
    if "predicted_anomaly" not in df.columns and "fused_any_flag" not in df.columns:
        raise ValueError(
            "Neither 'predicted_anomaly' nor 'fused_any_flag' found in predictions file."
        )
    missing = [c for c in required_min if c not in df.columns]
    if missing:
        raise ValueError(
            f"Predictions CSV missing required columns: {missing}. "
            f"Need at least: {required_min}."
        )

    # Fallback to labels CSV if is_anomaly or anomaly_type is missing.
    needs_labels = any(c not in df.columns for c in ["is_anomaly", "anomaly_type"])
    if needs_labels:
        if labels_path is None or not os.path.exists(labels_path):
            raise ValueError(
                "Predictions CSV is missing is_anomaly or anomaly_type, "
                f"and labels CSV is unavailable: {labels_path}"
            )
        labels_df = pd.read_csv(labels_path)
        # Take only join keys + label columns that exist in the labels CSV.
        cols_to_take = JOIN_KEYS + [
            c for c in LABEL_COLUMNS if c in labels_df.columns
        ]
        labels_df = labels_df[cols_to_take]
        # Only merge columns that are NOT already in df (avoid double-join).
        cols_to_add = [c for c in labels_df.columns if c not in df.columns]
        if cols_to_add:
            df = df.merge(
                labels_df[JOIN_KEYS + cols_to_add],
                on=JOIN_KEYS, how="left"
            )

    return df


# ----------------------------------------------------------------------
# Confusion matrix + aggregate metrics
# ----------------------------------------------------------------------
def compute_confusion(df: pd.DataFrame) -> dict:
    """
    Compute TP / FP / FN / TN.

    Definitions (EXACT, per spec):
        TP = is_anomaly==1 AND predicted_anomaly==1
        FP = is_anomaly==0 AND predicted_anomaly==1
        FN = is_anomaly==1 AND predicted_anomaly==0
        TN = is_anomaly==0 AND predicted_anomaly==0
    """
    # Drop rows missing either label or prediction.
    valid = df.dropna(subset=["is_anomaly", "predicted_anomaly"]).copy()
    y_true = valid["is_anomaly"].astype(int)
    y_pred = valid["predicted_anomaly"].astype(int)

    TP = int(((y_true == 1) & (y_pred == 1)).sum())
    FP = int(((y_true == 0) & (y_pred == 1)).sum())
    FN = int(((y_true == 1) & (y_pred == 0)).sum())
    TN = int(((y_true == 0) & (y_pred == 0)).sum())

    return {"TP": TP, "FP": FP, "FN": FN, "TN": TN}


def compute_aggregate_metrics(conf: dict) -> dict:
    """
    Compute aggregate metrics from confusion counts.

    Definitions (EXACT, per spec):
        Precision          = TP / (TP + FP)
        Recall             = TP / (TP + FN)
        F1                 = 2 * P * R / (P + R)
        Detection Rate     = Recall   (alias; reported under both names)
        False Alarm Rate   = FP / (FP + TN)
        Accuracy           = (TP + TN) / (TP + FP + FN + TN)
        Specificity        = TN / (TN + FP)
    All metrics use zero_division=0 (no crash on empty categories).
    """
    TP, FP, FN, TN = conf["TP"], conf["FP"], conf["FN"], conf["TN"]
    total = TP + FP + FN + TN

    precision = _safe_div(TP, TP + FP)
    recall = _safe_div(TP, TP + FN)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    detection_rate = recall  # alias
    false_alarm_rate = _safe_div(FP, FP + TN)
    accuracy = _safe_div(TP + TN, total)
    specificity = _safe_div(TN, TN + FP)

    return {
        "TP": TP,
        "FP": FP,
        "FN": FN,
        "TN": TN,
        "Precision": precision,
        "Recall": recall,
        "Detection_Rate": detection_rate,
        "F1": f1,
        "False_Alarm_Rate": false_alarm_rate,
        "Specificity": specificity,
        "Accuracy": accuracy,
        "Total_Rows_Evaluated": total,
        "Total_Actual_Anomalies": int(TP + FN),
        "Total_Predicted_Anomalies": int(TP + FP),
    }


# ----------------------------------------------------------------------
# Per-anomaly-type tables
# ----------------------------------------------------------------------
def compute_anomaly_type_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    TABLE 1: Sensor anomaly categories (is_anomaly == 1).

    Columns: anomaly_type, n_total, n_detected, n_missed, detection_rate.
    Sorted by n_total descending.

    For is_anomaly == 1 rows, a "false positive" is not defined by
    construction (those rows ARE real anomalies), so n_false_pos is
    intentionally NOT reported here.
    """
    sub = df[df["is_anomaly"] == 1].copy()
    rows = []
    # Discover anomaly types DYNAMICALLY (no hardcoded list).
    for atype, g in sub.groupby("anomaly_type"):
        n_total = len(g)
        n_detected = int((g["predicted_anomaly"] == 1).sum())
        n_missed = n_total - n_detected
        detection_rate = _safe_div(n_detected, n_total)
        rows.append({
            "anomaly_type": atype,
            "n_total": n_total,
            "n_detected": n_detected,
            "n_missed": n_missed,
            "detection_rate": detection_rate,
            "caveat": _small_sample_caveat(n_total),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("n_total", ascending=False).reset_index(drop=True)
    return out


def compute_weather_category_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    TABLE 2: Weather / normal categories (is_anomaly == 0).

    Columns: category, n_total, n_flagged_as_anomaly, false_alarm_rate.
    Sorted by n_total descending.

    The metric here is "false alarm rate" (fraction of these genuinely
    normal rows that the detector incorrectly flagged). It is NOT called
    "recall" because recall is not defined for is_anomaly == 0 rows.
    """
    sub = df[df["is_anomaly"] == 0].copy()
    rows = []
    for cat, g in sub.groupby("anomaly_type"):
        n_total = len(g)
        n_flagged = int((g["predicted_anomaly"] == 1).sum())
        far = _safe_div(n_flagged, n_total)
        rows.append({
            "category": cat,
            "n_total": n_total,
            "n_flagged_as_anomaly": n_flagged,
            "false_alarm_rate": far,
            "caveat": _small_sample_caveat(n_total),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("n_total", ascending=False).reset_index(drop=True)
    return out


def compute_weather_event_analysis(df: pd.DataFrame) -> dict:
    """
    Genuine weather event analysis.

    For each of {normal_weather_event, normal}:
      - n_total
      - n_false_alarms (rows flagged predicted_anomaly==1)
      - false_alarm_rate = n_false_alarms / n_total

    Reporting both lets the reader see whether genuine weather events
    are more or less likely to be misclassified than ordinary normal data.
    """
    result = {}
    for cat in ["normal_weather_event", "normal"]:
        sub = df[(df["is_anomaly"] == 0) & (df["anomaly_type"] == cat)]
        n_total = len(sub)
        n_false = int((sub["predicted_anomaly"] == 1).sum()) if n_total > 0 else 0
        far = _safe_div(n_false, n_total)
        result[cat] = {
            "n_total": n_total,
            "n_false_alarms": n_false,
            "false_alarm_rate": far,
            "caveat": _small_sample_caveat(n_total),
        }
    return result

def compute_per_severity_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute precision/recall per severity tier (High, Medium, Low).
    """
    if "severity" not in df.columns:
        return pd.DataFrame()

    rows = []
    for sev in ["High", "Medium", "Low"]:
        sub = df[df["severity"] == sev]
        if len(sub) == 0:
            continue
        y_true = sub["is_anomaly"].fillna(0).astype(int)
        y_pred = sub["predicted_anomaly"].fillna(0).astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        rows.append({
            "severity": sev,
            "n_alerts": tp + fp,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })
    return pd.DataFrame(rows)


def compute_per_station_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute precision/recall per station.
    """
    if "station_id" not in df.columns:
        return pd.DataFrame()

    rows = []
    for sid in sorted(df["station_id"].unique()):
        sub = df[df["station_id"] == sid]
        y_true = sub["is_anomaly"].fillna(0).astype(int)
        y_pred = sub["predicted_anomaly"].fillna(0).astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        rows.append({
            "station_id": sid,
            "n_alerts": tp + fp,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })
    return pd.DataFrame(rows)


def compute_confidence_calibration(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check whether confidence score correlates with accuracy.
    Buckets: High (80-100), Medium (50-79), Low (0-49)
    """
    if "anomaly_confidence" not in df.columns:
        return pd.DataFrame()

    alerts = df[df["predicted_anomaly"] == 1].copy()
    if len(alerts) == 0:
        return pd.DataFrame()

    def bucket(c):
        try:
            c = int(c)
        except (TypeError, ValueError):
            return "Unknown"
        if c >= 80:
            return "High (80-100)"
        if c >= 50:
            return "Medium (50-79)"
        return "Low (0-49)"

    alerts["confidence_bucket"] = alerts["anomaly_confidence"].apply(bucket)
    rows = []
    for b in ["High (80-100)", "Medium (50-79)", "Low (0-49)"]:
        sub = alerts[alerts["confidence_bucket"] == b]
        if len(sub) == 0:
            continue
        correct = int(sub["is_anomaly"].fillna(0).astype(int).sum())
        total = len(sub)
        accuracy = correct / total if total > 0 else 0.0
        rows.append({
            "confidence_bucket": b,
            "n_alerts": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
        })
    return pd.DataFrame(rows)
# ----------------------------------------------------------------------
# Score distribution
# ----------------------------------------------------------------------
def compute_score_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Min / mean / max of anomaly_score separately for TP / FP / FN / TN.

    Tells the reader whether the threshold is calibrated such that
    anomaly scores for TP are clearly lower (more anomalous) than for FP.
    Returns an empty DataFrame if anomaly_score is missing.
    """
    if "anomaly_score" not in df.columns:
        return pd.DataFrame()
    valid = df.dropna(subset=["is_anomaly", "predicted_anomaly",
                              "anomaly_score"]).copy()
    if valid.empty:
        return pd.DataFrame()

    valid["is_anomaly"] = valid["is_anomaly"].astype(int)
    valid["predicted_anomaly"] = valid["predicted_anomaly"].astype(int)

    def _classify(row):
        if row["is_anomaly"] == 1 and row["predicted_anomaly"] == 1:
            return "TP"
        if row["is_anomaly"] == 0 and row["predicted_anomaly"] == 1:
            return "FP"
        if row["is_anomaly"] == 1 and row["predicted_anomaly"] == 0:
            return "FN"
        if row["is_anomaly"] == 0 and row["predicted_anomaly"] == 0:
            return "TN"
        return "Other"

    valid["category"] = valid.apply(_classify, axis=1)

    rows = []
    for cat in ["TP", "FP", "FN", "TN"]:
        sub = valid[valid["category"] == cat]
        if len(sub) > 0:
            rows.append({
                "category": cat,
                "n": len(sub),
                "min": float(sub["anomaly_score"].min()),
                "mean": float(sub["anomaly_score"].mean()),
                "max": float(sub["anomaly_score"].max()),
            })
        else:
            # Empty category - report n=0 with NaN for stats.
            rows.append({
                "category": cat,
                "n": 0,
                "min": float("nan"),
                "mean": float("nan"),
                "max": float("nan"),
            })
    return pd.DataFrame(rows)

def compute_per_severity_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Compute precision/recall per severity tier."""
    if "severity" not in df.columns:
        return pd.DataFrame()

    rows = []
    for sev in ["High", "Medium", "Low"]:
        sub = df[df["severity"] == sev]
        if len(sub) == 0:
            continue
        y_true = sub["is_anomaly"].fillna(0).astype(int)
        y_pred = sub["predicted_anomaly"].fillna(0).astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        rows.append({
            "severity": sev,
            "n_alerts": tp + fp,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })
    return pd.DataFrame(rows)


def compute_per_station_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Compute precision/recall per station."""
    if "station_id" not in df.columns:
        return pd.DataFrame()

    rows = []
    for sid in sorted(df["station_id"].unique()):
        sub = df[df["station_id"] == sid]
        y_true = sub["is_anomaly"].fillna(0).astype(int)
        y_pred = sub["predicted_anomaly"].fillna(0).astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        rows.append({
            "station_id": sid,
            "n_alerts": tp + fp,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })
    return pd.DataFrame(rows)


def compute_confidence_calibration(df: pd.DataFrame) -> pd.DataFrame:
    """Check whether confidence score correlates with accuracy."""
    if "anomaly_confidence" not in df.columns:
        return pd.DataFrame()

    alerts = df[df["predicted_anomaly"] == 1].copy()
    if len(alerts) == 0:
        return pd.DataFrame()

    def bucket(c):
        try:
            c = int(c)
        except (TypeError, ValueError):
            return "Unknown"
        if c >= 80:
            return "High (80-100)"
        if c >= 50:
            return "Medium (50-79)"
        return "Low (0-49)"

    alerts["confidence_bucket"] = alerts["anomaly_confidence"].apply(bucket)
    rows = []
    for b in ["High (80-100)", "Medium (50-79)", "Low (0-49)"]:
        sub = alerts[alerts["confidence_bucket"] == b]
        if len(sub) == 0:
            continue
        correct = int(sub["is_anomaly"].fillna(0).astype(int).sum())
        total = len(sub)
        accuracy = correct / total if total > 0 else 0.0
        rows.append({
            "confidence_bucket": b,
            "n_alerts": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
        })
    return pd.DataFrame(rows)
# ----------------------------------------------------------------------
# Formatting (human-readable summary, also written to .txt)
# ----------------------------------------------------------------------
def format_summary(df: pd.DataFrame,
                   agg: dict,
                   conf: dict,
                   anomaly_type_df: pd.DataFrame,
                   weather_cat_df: pd.DataFrame,
                   weather_event_analysis: dict,
                   score_dist_df: pd.DataFrame,
                   n_total_rows: int) -> str:
    """Format the full summary text (printed to stdout and saved to .txt)."""
    lines = []
    lines.append("=" * 70)
    lines.append("SkyGuard AI - Evaluation Harness")
    lines.append("=" * 70)

    lines.append("")
    lines.append("INPUT SUMMARY")
    lines.append(f"  Total rows in predictions CSV      : {n_total_rows}")
    lines.append(f"  Total rows evaluated (with labels) : {agg['Total_Rows_Evaluated']}")
    lines.append(f"  Total actual anomalies             : {agg['Total_Actual_Anomalies']}")
    lines.append(f"  Total predicted anomalies          : {agg['Total_Predicted_Anomalies']}")

    # Confusion matrix
    lines.append("")
    lines.append("CONFUSION MATRIX")
    lines.append("                    Pred Normal    Pred Anomaly")
    lines.append(f"  Actual Normal     {conf['TN']:<14} {conf['FP']:<14}")
    lines.append(f"  Actual Anomaly    {conf['FN']:<14} {conf['TP']:<14}")

    # Aggregate metrics
    lines.append("")
    lines.append("AGGREGATE METRICS")
    lines.append(f"  TP / FP / FN / TN  : {agg['TP']} / {agg['FP']} / {agg['FN']} / {agg['TN']}")
    lines.append(f"  Precision          : {agg['Precision']:.4f}")
    lines.append(f"  Recall             : {agg['Recall']:.4f}")
    lines.append(f"  Detection Rate     : {agg['Detection_Rate']:.4f}   (alias of Recall)")
    lines.append(f"  F1                 : {agg['F1']:.4f}")
    lines.append(f"  False Alarm Rate   : {agg['False_Alarm_Rate']:.4f}")
    lines.append(f"  Specificity        : {agg['Specificity']:.4f}")
    lines.append(f"  Accuracy           : {agg['Accuracy']:.4f}")

    # Table 1 - sensor anomaly categories
    lines.append("")
    lines.append("TABLE 1 - SENSOR ANOMALY CATEGORIES (is_anomaly == 1)")
    if anomaly_type_df.empty:
        lines.append("  (no rows)")
    else:
        for _, r in anomaly_type_df.iterrows():
            lines.append(
                f"  {str(r['anomaly_type']):<28s}"
                f"    n_total={int(r['n_total']):>5}"
                f"    n_detected={int(r['n_detected']):>5}"
                f"    n_missed={int(r['n_missed']):>5}"
                f"    detection_rate={r['detection_rate']:.4f}{r['caveat']}"
            )

    # Table 2 - weather / normal categories
    lines.append("")
    lines.append("TABLE 2 - WEATHER / NORMAL CATEGORIES (is_anomaly == 0)")
    if weather_cat_df.empty:
        lines.append("  (no rows)")
    else:
        for _, r in weather_cat_df.iterrows():
            lines.append(
                f"  {str(r['category']):<28s}"
                f"    n_total={int(r['n_total']):>5}"
                f"    n_flagged_as_anomaly={int(r['n_flagged_as_anomaly']):>5}"
                f"    false_alarm_rate={r['false_alarm_rate']:.4f}{r['caveat']}"
            )

    # Weather event analysis
    lines.append("")
    lines.append("GENUINE WEATHER EVENT ANALYSIS")
    for cat in ["normal_weather_event", "normal"]:
        d = weather_event_analysis.get(cat, {})
        lines.append(f"  {cat}:")
        lines.append(f"    n_normal_weather_events (n_total) = {d.get('n_total', 0)}")
        lines.append(f"    n_false_alarms_on_weather_events = {d.get('n_false_alarms', 0)}")
        lines.append(
            f"    false_alarm_rate_on_weather_events = "
            f"{d.get('false_alarm_rate', 0.0):.4f}{d.get('caveat', '')}"
        )

    # Score distribution
    if not score_dist_df.empty:
        lines.append("")
        lines.append("SCORE DISTRIBUTION BY CONFUSION CATEGORY (anomaly_score)")
        for _, r in score_dist_df.iterrows():
            if r["n"] == 0:
                lines.append(
                    f"  {str(r['category']):<6s}"
                    f"    n={int(r['n']):>5}"
                    f"    min=n/a    mean=n/a    max=n/a"
                )
            else:
                lines.append(
                    f"  {str(r['category']):<6s}"
                    f"    n={int(r['n']):>5}"
                    f"    min={r['min']:.4f}    mean={r['mean']:.4f}    max={r['max']:.4f}"
                )
    # ------------------ Per-severity breakdown ------------------
    severity_df = compute_per_severity_breakdown(df)
    if not severity_df.empty:
        lines.append("")
        lines.append("=" * 70)
        lines.append("PER-SEVERITY BREAKDOWN")
        lines.append("=" * 70)
        lines.append(severity_df.to_string(index=False))

    # ------------------ Per-station breakdown ------------------
    station_df = compute_per_station_breakdown(df)
    if not station_df.empty:
        lines.append("")
        lines.append("=" * 70)
        lines.append("PER-STATION BREAKDOWN")
        lines.append("=" * 70)
        lines.append(station_df.to_string(index=False))

    # ------------------ Confidence calibration ------------------
    calib_df = compute_confidence_calibration(df)
    if not calib_df.empty:
        lines.append("")
        lines.append("=" * 70)
        lines.append("CONFIDENCE CALIBRATION")
        lines.append("=" * 70)
        lines.append(calib_df.to_string(index=False))

    
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Save results
# ----------------------------------------------------------------------
def save_results(metrics_csv: str,
                 summary_txt: str,
                 agg: dict,
                 anomaly_type_df: pd.DataFrame,
                 weather_cat_df: pd.DataFrame,
                 weather_event_analysis: dict,
                 score_dist_df: pd.DataFrame,
                 summary_text: str) -> None:
    """
    Save:
      - machine-readable CSV (one row per metric per block, long format),
      - human-readable .txt summary (identical to stdout).
    """
    os.makedirs(os.path.dirname(metrics_csv), exist_ok=True)

    # ---- Machine-readable CSV (long format) ----
    rows = []

    # Aggregate block: one row per metric.
    for k, v in agg.items():
        rows.append({"block": "aggregate", "metric": k, "value": v})

    # Anomaly type block: one row per anomaly_type.
    if not anomaly_type_df.empty:
        for _, r in anomaly_type_df.iterrows():
            rows.append({
                "block": "anomaly_type",
                "category": r["anomaly_type"],
                "n_total": int(r["n_total"]),
                "n_detected": int(r["n_detected"]),
                "n_missed": int(r["n_missed"]),
                "detection_rate": float(r["detection_rate"]),
            })

    # Weather category block: one row per category.
    if not weather_cat_df.empty:
        for _, r in weather_cat_df.iterrows():
            rows.append({
                "block": "weather_category",
                "category": r["category"],
                "n_total": int(r["n_total"]),
                "n_flagged_as_anomaly": int(r["n_flagged_as_anomaly"]),
                "false_alarm_rate": float(r["false_alarm_rate"]),
            })

    # Weather event analysis block: one row per category.
    for cat, d in weather_event_analysis.items():
        rows.append({
            "block": "weather_event_analysis",
            "category": cat,
            "n_total": int(d["n_total"]),
            "n_false_alarms": int(d["n_false_alarms"]),
            "false_alarm_rate": float(d["false_alarm_rate"]),
        })

    # Score distribution block: one row per confusion category.
    if not score_dist_df.empty:
        for _, r in score_dist_df.iterrows():
            rows.append({
                "block": "score_distribution",
                "category": r["category"],
                "n": int(r["n"]),
                "min": float(r["min"]) if not pd.isna(r["min"]) else None,
                "mean": float(r["mean"]) if not pd.isna(r["mean"]) else None,
                "max": float(r["max"]) if not pd.isna(r["max"]) else None,
            })

    pd.DataFrame(rows).to_csv(metrics_csv, index=False)

    # ---- Human-readable summary (.txt) ----
    os.makedirs(os.path.dirname(summary_txt), exist_ok=True)
    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write(summary_text)


# ----------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SkyGuard AI read-only evaluation harness."
    )
    parser.add_argument(
        "--predictions",
        default=DEFAULT_PREDICTIONS,
        help=f"Path to predictions CSV (default: {DEFAULT_PREDICTIONS})",
    )
    parser.add_argument(
        "--labels",
        default=DEFAULT_LABELS,
        help=f"Path to labels CSV fallback (default: {DEFAULT_LABELS})",
    )
    args = parser.parse_args()

    # 1. Load predictions (and join labels if needed).
    df = load_predictions(args.predictions, args.labels)
    n_total_rows = len(df)

    # 2. Compute confusion matrix.
    conf = compute_confusion(df)

    # 3. Compute aggregate metrics.
    agg = compute_aggregate_metrics(conf)

    # 4. Compute per-anomaly-type tables (split by is_anomaly).
    anomaly_type_df = compute_anomaly_type_metrics(df)
    weather_cat_df = compute_weather_category_metrics(df)

    # 5. Compute genuine weather event analysis.
    weather_event_analysis = compute_weather_event_analysis(df)

    # 6. Compute score distribution (TP/FP/FN/TN).
    score_dist_df = compute_score_distribution(df)

    # 7. Format the summary text (printed to stdout AND saved to .txt).
    summary_text = format_summary(
        df, agg, conf, anomaly_type_df, weather_cat_df,
        weather_event_analysis, score_dist_df, n_total_rows
    )
    print(summary_text)

    # 8-9. Save machine-readable CSV + human-readable .txt summary.
    save_results(
        METRICS_CSV, SUMMARY_TXT,
        agg, anomaly_type_df, weather_cat_df,
        weather_event_analysis, score_dist_df, summary_text
    )
    print(f"\n[save] Machine-readable metrics -> {METRICS_CSV}")
    print(f"[save] Human-readable summary  -> {SUMMARY_TXT}")


if __name__ == "__main__":
    main()