"""
src/ml_detector.py
SkyGuard AI - STEP 11: Isolation Forest baseline anomaly detector.

First unsupervised baseline. Trains IsolationForest on the NORMAL AWS
data only, then scores the injected test set. Uses 6 baseline features
(raw + first-difference); temporal/seasonal features are intentionally
excluded and will be tested in a later experiment.

REUSES src.feature_engineering.build_features() - does NOT duplicate
feature-engineering logic.

Ground-truth columns (is_anomaly, anomaly_type, injected_parameter) are
ONLY used for post-prediction evaluation and are NEVER passed to the
IsolationForest.
"""

import os
import sys

# ----------------------------------------------------------------------
# Sibling import shim: make src/feature_engineering.py importable whether
# this file is run as `python src/ml_detector.py`, `python -m src.ml_detector`,
# or from an IDE. Python normally adds the script's own directory to
# sys.path[0] for the `python src/ml_detector.py` case; we add it explicitly
# here so the import also works under `python -m`.
# ----------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)
import joblib

from feature_engineering import build_features  # noqa: E402


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
RANDOM_STATE = 42

NORMAL_CSV = "data/normal_aws_data.csv"
TEST_CSV = "data/test_injected_aws.csv"

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest.pkl")

PREDICTIONS_CSV = "data/isolation_forest_predictions.csv"

# Baseline features ONLY (raw + first-difference). Temporal/seasonal
# features (hour, hour_sin, hour_cos, day_of_year, doy_sin, doy_cos)
# are intentionally excluded for this first experiment.
BASELINE_FEATURE_COLUMNS = [
    "temperature",
    "pressure",
    "humidity",
    "d_temperature",
    "d_pressure",
    "d_humidity",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
]

# Ground-truth columns passed through to the prediction output for later
# evaluation. NEVER used as model input features.
LABEL_COLUMNS = ["is_anomaly", "anomaly_type", "injected_parameter"]

# Canonical column order in the prediction CSV.
OUTPUT_COLUMNS = [
    "timestamp",
    "station_id",
    "is_anomaly",
    "anomaly_type",
    "injected_parameter",
    "predicted_anomaly",
    "anomaly_score",
]


# ----------------------------------------------------------------------
# Training
# ----------------------------------------------------------------------
def train_isolation_forest(normal_csv: str = NORMAL_CSV) -> IsolationForest:
    """
    Train an IsolationForest baseline on NORMAL AWS data only.

    Pipeline:
      1. Load normal_aws_data.csv (read-only).
      2. build_features() to compute d_temperature / d_pressure / d_humidity.
      3. Select the 6 BASELINE_FEATURE_COLUMNS.
      4. Drop rows where any baseline feature is NaN (the first row of
         each station has NaN d_* by design - we do NOT fill with 0).
      5. Fit IsolationForest(n_estimators=200, contamination=0.02,random_state=42) on the 6 features.

    Returns
    -------
    IsolationForest
        Fitted model ready for scoring.
    """
    # 1. Load normal data (read-only - we never write back to it).
    df = pd.read_csv(normal_csv)

    # 2. Build features via the shared module (no duplication).
    feats = build_features(df)

    # 3-4. Select baseline features and drop rows with any NaN.
    # We DO NOT fill d_* NaN with 0: a fake "no change" would look
    # exactly like the frozen-sensor anomaly we are trying to detect.
    X = feats[BASELINE_FEATURE_COLUMNS].copy()
    mask = X.notna().all(axis=1)
    X_train = X[mask].to_numpy()

    print(f"[train] Normal rows loaded      : {len(feats)}")
    print(f"[train] Rows used for training  : {len(X_train)} "
          f"(dropped {len(feats) - len(X_train)} first-row-per-station)")

    # 5. Fit Isolation Forest with baseline (NOT tuned) parameters.
    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,   # ~2% expected anomaly rate
        random_state=RANDOM_STATE,
    )
    model.fit(X_train)
    print(f"[train] IsolationForest fitted. "
          f"n_estimators={model.n_estimators}, "
          f"contamination={model.contamination}")
    return model


# ----------------------------------------------------------------------
# Prediction
# ----------------------------------------------------------------------
def predict_test(model: IsolationForest,
                 test_csv: str = TEST_CSV) -> pd.DataFrame:
    """
    Score the test set using the trained IsolationForest.

    Pipeline:
      1. Load test_injected_aws.csv (read-only).
      2. build_features() to compute d_* features identically to training.
      3. Build a parallel "meta" DataFrame with timestamp, station_id,
         and any present ground-truth columns so row alignment is
         preserved between the feature matrix X and the prediction output.
      4. Filter X to rows where all BASELINE_FEATURE_COLUMNS are non-NaN
         (drops the first row of each station - NEVER fills with 0).
         The same row mask is applied to meta, so X and meta stay aligned
         index-for-index.
      5. Predict: model.predict -> {-1: anomaly, +1: normal}.
      6. Score:  anomaly_score = model.decision_function (SHIFTED score;
                 0 = contamination boundary; more negative = more anomalous).
                 We use decision_function (NOT score_samples) so the meaning
                 of the column is unambiguous.
      7. Convert to clearer columns:
         - predicted_anomaly: 1 = anomaly, 0 = normal.
         - anomaly_score: decision_function output (kept as-is).

    Ground-truth columns are PASSED THROUGH to the output for evaluation,
    and NEVER fed to the model. If they are absent from the test input,
    they are inserted as NaN (we do NOT hard-require them).

    Returns
    -------
    pd.DataFrame
        Output with the canonical OUTPUT_COLUMNS order. Only rows where X
        was non-NaN are returned (the first row of each station is dropped).
    """
    # 1. Load test data (read-only).
    df = pd.read_csv(test_csv)

    # 2. Build features identically to training.
    feats = build_features(df)

    # 3. Build meta DataFrame preserving alignment. Do NOT reset_index
    #    here, so meta's index matches X's index exactly.
    available_meta = ["timestamp", "station_id"] + [
        c for c in LABEL_COLUMNS if c in feats.columns
    ]
    meta = feats[available_meta].copy()

    # 4. Build X and filter rows where all baseline features are non-NaN.
    X = feats[BASELINE_FEATURE_COLUMNS].copy()
    mask = X.notna().all(axis=1)
    X_score = X[mask]
    meta_score = meta.loc[mask]

    # Sanity check: X and meta must stay aligned by index.
    assert X_score.index.equals(meta_score.index), \
        "Row alignment broken between X and meta."

    print(f"[predict] Test rows loaded       : {len(feats)}")
    print(f"[predict] Rows used for prediction: {len(X_score)} "
          f"(dropped {len(feats) - len(X_score)} first-row-per-station)")

    # 5. Predict: raw output convention is {-1: anomaly, +1: normal}.
    raw_pred = model.predict(X_score.to_numpy())

    # 6. Score via decision_function (NOT score_samples).
    #    decision_function returns a SHIFTED score: 0 is the contamination
    #    boundary, more negative = more anomalous.
    anomaly_score = model.decision_function(X_score.to_numpy())

    # 7. Convert to clearer 0/1 convention: 1 = anomaly, 0 = normal.
    predicted_anomaly = (raw_pred == -1).astype(int)

    # Assemble output, preserving alignment.
    out = meta_score.copy()
    out["predicted_anomaly"] = predicted_anomaly
    out["anomaly_score"] = anomaly_score

    # Insert any missing label columns as NaN (do NOT hard-require them).
    for col in LABEL_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    # Reorder to canonical output order.
    out = out[OUTPUT_COLUMNS]

    # NOTE: we deliberately do NOT cast is_anomaly dtype - retain as-is
    # from the input (so 0/1 stays 0/1, not float).
    return out


# ----------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------
def evaluate_predictions(pred_df: pd.DataFrame) -> None:
    """
    Print basic evaluation statistics if ground-truth is available.

    Ground-truth is ONLY used here (post-prediction) - never for training,
    fitting, tuning, or predicting.
    """
    print("=" * 70)
    print("SkyGuard AI - Isolation Forest baseline evaluation")
    print("=" * 70)

    n_test = len(pred_df)
    print(f"Number of test rows           : {n_test}")

    # Always print distribution of predicted anomalies.
    print("\nDistribution of predicted_anomaly (0=normal, 1=anomaly):")
    print(pred_df["predicted_anomaly"].value_counts().to_string())

    # Skip the metric block if is_anomaly is missing or all-NaN.
    if "is_anomaly" not in pred_df.columns or pred_df["is_anomaly"].isna().all():
        print("\n[WARNING] Ground-truth is_anomaly is not available.")
        print("Skipping metric block (precision / recall / F1).")
        return

    # Restrict to rows with a valid is_anomaly label.
    labeled = pred_df[pred_df["is_anomaly"].notna()]
    y_true = labeled["is_anomaly"].astype(int).to_numpy()
    y_pred = labeled["predicted_anomaly"].astype(int).to_numpy()

    n_actual_anom = int((y_true == 1).sum())
    n_pred_anom = int((y_pred == 1).sum())
    n_actual_norm = int((y_true == 0).sum())
    n_pred_norm = int((y_pred == 0).sum())

    print(f"\nNumber of actual anomalies     : {n_actual_anom}")
    print(f"Number of predicted anomalies  : {n_pred_anom}")
    print(f"Number of actual normal rows   : {n_actual_norm}")
    print(f"Number of predicted normal rows: {n_pred_norm}")

    # Confusion matrix: rows=true [normal, anomaly], cols=pred [normal, anomaly].
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    print("\nConfusion matrix "
          "(rows=true [normal, anomaly], cols=pred [normal, anomaly]):")
    print(f"  true normal    | pred normal: {cm[0, 0]:>6}  "
          f"pred anomaly: {cm[0, 1]:>6}")
    print(f"  true anomaly   | pred normal: {cm[1, 0]:>6}  "
          f"pred anomaly: {cm[1, 1]:>6}")

       # zero_division=0 so we get 0.0 instead of a crash when nothing is
    # predicted as anomaly (contamination=0.02 sets the expected rate).
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    print(f"\nPrecision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1-score : {f1:.4f}")

    print("\nNote: contamination='0.02' is used only as a baseline setting.")
    print("These results are not considered optimal. Further experiments")
    print("will evaluate whether additional features, QC rules, or")
    print("hyperparameter tuning improve anomaly detection performance.")

# ----------------------------------------------------------------------
# Persistence helpers
# ----------------------------------------------------------------------
def save_model(model: IsolationForest, path: str = MODEL_PATH) -> None:
    """Persist the trained model with joblib. Creates the dir if missing."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    print(f"[save] Model saved to: {path}")


def save_predictions(pred_df: pd.DataFrame,
                     path: str = PREDICTIONS_CSV) -> None:
    """Persist prediction results as CSV. Creates the dir if missing."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pred_df.to_csv(path, index=False)
    print(f"[save] Predictions saved to: {path}")


# ----------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("SkyGuard AI - STEP 11: Isolation Forest baseline")
    print("=" * 70)

    # 1-4. Train on NORMAL data only.
    print()
    model = train_isolation_forest(NORMAL_CSV)

    # 5. Save the model.
    print()
    save_model(model, MODEL_PATH)

    # 6-7. Build features for the injected test dataset and predict.
    print()
    pred_df = predict_test(model, TEST_CSV)

    # 8. Save prediction results.
    print()
    save_predictions(pred_df, PREDICTIONS_CSV)

    # 9. Print basic evaluation statistics.
    print()
    evaluate_predictions(pred_df)