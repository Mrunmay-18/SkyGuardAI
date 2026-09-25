"""
src/anomaly_classifier.py
SkyGuard AI - STEP 17: Rule-Based Anomaly Classification.

EXPLAINABLE RULE-BASED classification layer. It does NOT detect
anomalies from scratch — it INTERPRETS the evidence produced by the
four existing detectors (Isolation Forest, QC engine, spatial
analysis, temporal detector) and assigns a human-readable anomaly
class.

Confidence levels ("high", "medium", "low") are RULE-BASED
CATEGORICAL labels, NOT calibrated probabilities:
    "high":   a specific, direct detector signal supports the class
              (e.g., qc_gap_flag fires → the gap rule is a direct
              match).
    "medium": multiple weak signals support the class, OR a single
              signal whose meaning requires interpretation (e.g.,
              qc_internal_flag requires reading the reason text).
    "low":    only indirect or supporting evidence supports the class
              (e.g., spatial_isolation is supporting, not proof).

State explicitly: this is NOT a calibrated probability. It is a
rule-based descriptive category.

Does NOT modify any existing file. Uses pandas and numpy only.
"""

import os
import sys

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Class name constants
# ----------------------------------------------------------------------
CLASS_COMM_FAILURE = "Communication Failure"
CLASS_FROZEN = "Frozen Sensor"
CLASS_SPIKE = "Temperature Spike"
CLASS_DROP = "Temperature Drop"
CLASS_MULTI = "Multivariate Inconsistency"
CLASS_DRIFT = "Calibration Drift"
CLASS_WEATHER = "Possible Genuine Weather Event"
CLASS_LIKELY_SENSOR = "Likely Sensor/Data Anomaly"
CLASS_UNCLASSIFIED = "Unclassified"
CLASS_NORMAL = "Normal"


# ----------------------------------------------------------------------
# Safe column access helpers
# ----------------------------------------------------------------------
def _build_cols_dict(df: pd.DataFrame) -> dict:
    """
    Extract all needed columns into a dict of numpy arrays.

    Missing columns are filled with defaults (0 for int, NaN for float,
    "" for str) so the classifier never crashes on missing evidence.
    """
    n = len(df)
    cols = {}

    # Integer flag columns (missing → 0).
    int_cols = [
        "qc_gap_flag", "qc_persistence_flag", "qc_internal_flag",
        "qc_temporal_flag", "qc_any_flag", "predicted_anomaly",
        "spatial_isolated_flag", "spatial_common_event_flag",
        "temporal_level1_flag", "temporal_level2_flag",
        "temporal_predicted_anomaly",
    ]
    for col in int_cols:
        if col in df.columns:
            cols[col] = df[col].fillna(0).astype(int).to_numpy()
        else:
            cols[col] = np.zeros(n, dtype=int)

    # Float columns (missing → NaN).
    float_cols = [
        "temporal_z_4", "temporal_z_8", "temporal_z_16",
    ]
    for col in float_cols:
        if col in df.columns:
            cols[col] = df[col].to_numpy(dtype=float)
        else:
            cols[col] = np.full(n, np.nan)

    # String columns (missing → "").
    str_cols = [
        "qc_gap_reason", "qc_persistence_reason", "qc_internal_reason",
        "qc_temporal_reason", "qc_reasons", "temporal_reason",
        "spatial_isolated_reason", "spatial_common_event_reason",
    ]
    for col in str_cols:
        if col in df.columns:
            cols[col] = df[col].fillna("").astype(str).to_numpy()
        else:
            cols[col] = np.array([""] * n, dtype=object)

    return cols


def _get_reason(cols: dict, i: int, reason_col: str,
                fallback_col: str = "qc_reasons",
                default: str = "reason not available") -> str:
    """
    Get a specific reason string at row i. Falls back to the
    aggregated qc_reasons column, then to a default string.
    """
    val = cols.get(reason_col, np.array([]))
    if i < len(val) and val[i]:
        return str(val[i])
    fb = cols.get(fallback_col, np.array([]))
    if i < len(fb) and fb[i]:
        return str(fb[i])
    return default


def _determine_direction_from_qc_reason(reason: str) -> str | None:
    """
    Try to determine temperature-change direction from a QC temporal
    reason string. Returns "spike", "drop", or None.

    The QC temporal reason format is:
        "large change in temperature (d=5.920, k*sigma=5.457)"
    The sign of d tells us the direction.
    """
    if not reason:
        return None
    # Only attempt to parse temperature-related reasons.
    if "temperature" not in reason.lower():
        return None
    # Find "d=" and parse the numeric value.
    if "d=" not in reason:
        return None
    try:
        d_part = reason.split("d=")[1].split(",")[0].split(")")[0]
        d_val = float(d_part)
        if d_val > 0:
            return "spike"
        elif d_val < 0:
            return "drop"
    except (ValueError, IndexError):
        pass
    return None


# ----------------------------------------------------------------------
# Per-row classification
# ----------------------------------------------------------------------
def _classify_row(cols: dict, i: int) -> tuple:
    """
    Classify a single row using priority-ordered rules.

    Returns (anomaly_class, confidence, reason).
    """
    # ---- Contradictory spatial evidence (mandatory override) ----
    # Checked BEFORE priority rules; takes precedence over rules 6 and 7.
    spatial_iso = int(cols["spatial_isolated_flag"][i])
    spatial_com = int(cols["spatial_common_event_flag"][i])

    if spatial_iso == 1 and spatial_com == 1:
        return (
            CLASS_UNCLASSIFIED,
            "low",
            "Spatial evidence is contradictory: isolated deviation AND "
            "common-event evidence both fired; manual review recommended.",
        )

    # ---- Priority 1: Communication Failure ----
    if int(cols["qc_gap_flag"][i]) == 1:
        reason = _get_reason(cols, i, "qc_gap_reason")
        return (
            CLASS_COMM_FAILURE,
            "high",
            f"QC gap flag fired: {reason}",
        )

    # ---- Priority 2: Frozen Sensor ----
    if int(cols["qc_persistence_flag"][i]) == 1:
        reason = _get_reason(cols, i, "qc_persistence_reason")
        return (
            CLASS_FROZEN,
            "high",
            f"QC persistence flag fired: {reason}",
        )

    # ---- Priority 3: Temperature Spike / Temperature Drop ----
    l1 = int(cols["temporal_level1_flag"][i])
    if l1 == 1:
        z4 = cols["temporal_z_4"][i]
        z8 = cols["temporal_z_8"][i]
        z16 = cols["temporal_z_16"][i]

        # Find the largest-magnitude non-NaN z that exceeds the L1
        # threshold (K_HIGH=3.0 from the temporal detector).
        candidates = []
        for z, w in [(z4, 4), (z8, 8), (z16, 16)]:
            if not np.isnan(z) and abs(z) > 3.0:
                candidates.append((abs(z), z, w))

        if candidates:
            candidates.sort(reverse=True)
            _, triggering_z, triggering_w = candidates[0]
            if triggering_z > 0:
                cls = CLASS_SPIKE
            else:
                cls = CLASS_DROP
            return (
                cls,
                "high",
                f"Sudden temperature change detected: "
                f"z_4={z4:.2f}, z_8={z8:.2f}, z_16={z16:.2f} "
                f"(temporal_level1_flag fired)",
            )
        else:
            # Fallback: use qc_temporal_flag to determine direction.
            qc_temp = int(cols["qc_temporal_flag"][i])
            if qc_temp == 1:
                qc_reason = _get_reason(
                    cols, i, "qc_temporal_reason", default=""
                )
                direction = _determine_direction_from_qc_reason(qc_reason)
                if direction == "spike":
                    return (
                        CLASS_SPIKE, "high",
                        f"Sudden temperature change (from QC temporal): "
                        f"{qc_reason}",
                    )
                elif direction == "drop":
                    return (
                        CLASS_DROP, "high",
                        f"Sudden temperature change (from QC temporal): "
                        f"{qc_reason}",
                    )
                # Direction undetermined.
                return (
                    CLASS_UNCLASSIFIED, "high",
                    f"Temporal L1 fired but direction undetermined; "
                    f"QC temporal reason: {qc_reason}",
                )
            # No QC temporal fallback either.
            return (
                CLASS_UNCLASSIFIED, "high",
                "Temporal L1 fired but no z exceeded threshold and no "
                "QC temporal direction available",
            )

    # ---- Priority 4: Multivariate Inconsistency ----
    if int(cols["qc_internal_flag"][i]) == 1:
        reason = _get_reason(cols, i, "qc_internal_reason")
        return (
            CLASS_MULTI,
            "medium",
            f"QC internal consistency flag fired: {reason}",
        )

    # ---- Priority 5: Calibration Drift ----
    # Level-2 temporal persistence alone is not sufficient evidence
    # to assign a specific Calibration Drift class.
    #
    # The investigation showed that Level-2 persistence occurs frequently
    # in normal data and that IF/QC/spatial support does not reliably
    # distinguish calibration drift from other anomaly types.
    #
    # Therefore, ambiguous Level-2 persistence remains Unclassified.

    l2 = int(cols["temporal_level2_flag"][i])

    if l2 == 1 and l1 == 0:
        temp_reason = cols.get("temporal_reason", np.array([]))
        tr = str(temp_reason[i]) if i < len(temp_reason) else ""

        return (
            CLASS_UNCLASSIFIED,
            "low",
            f"Persistent temporal deviation detected, but evidence "
            f"is insufficient to confidently classify calibration drift. "
            f"{tr}",
        )
    # ---- Priority 6: Possible Genuine Weather Event ----
    if spatial_com == 1 and spatial_iso == 0:
        com_reason = cols.get("spatial_common_event_reason", np.array([]))
        cr = str(com_reason[i]) if i < len(com_reason) else ""
        return (
            CLASS_WEATHER,
            "low",
            f"Nearby stations show a common change; possible regional "
            f"weather event. {cr}",
        )

    # ---- Priority 7: Likely Sensor/Data Anomaly ----
    if spatial_iso == 1:
        iso_reason = cols.get("spatial_isolated_reason", np.array([]))
        ir = str(iso_reason[i]) if i < len(iso_reason) else ""
        return (
            CLASS_LIKELY_SENSOR,
            "low",
            f"Station deviates from nearby stations while neighbours "
            f"remain consistent. {ir}",
        )

    # ---- Priority 8: Anomaly evidence present but no specific class ----
    if_pred = int(cols["predicted_anomaly"][i])
    qc_any = int(cols["qc_any_flag"][i])
    temp_pred = int(cols["temporal_predicted_anomaly"][i])

    if if_pred == 1 or qc_any == 1 or spatial_iso == 1 or temp_pred == 1:
        return (
            CLASS_UNCLASSIFIED,
            "low",
            "Anomaly evidence detected, but available signals are "
            "insufficient to assign a specific anomaly class.",
        )

    # ---- Priority 9: No evidence ----
    return (CLASS_NORMAL, "high", "No anomaly evidence from any detector.")


# ----------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------
def classify_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify anomalies in a DataFrame using rule-based priority ordering.

    The input must contain columns from the verified input schema
    (station_id, timestamp, and detector output columns). Missing
    columns are tolerated — treated as zero/absent evidence.

    Parameters
    ----------
    df : pd.DataFrame
        Joined observations with detector outputs.

    Returns
    -------
    pd.DataFrame
        Copy of df with ADDED columns:
          anomaly_class              (str)
          anomaly_class_confidence   ("high" | "medium" | "low")
          anomaly_class_reason       (str)
        The input is NOT mutated.

    Confidence is a RULE-BASED CATEGORICAL label, NOT a calibrated
    probability. See the module docstring for the confidence definitions.
    """
    out = df.copy()
    n = len(out)

    # Precompute all needed columns as arrays (missing → defaults).
    cols = _build_cols_dict(out)

    # Classify each row.
    classes = [""] * n
    confidences = [""] * n
    reasons = [""] * n

    for i in range(n):
        cls, conf, reason = _classify_row(cols, i)
        classes[i] = cls
        confidences[i] = conf
        reasons[i] = reason

    out["anomaly_class"] = classes
    out["anomaly_class_confidence"] = confidences
    out["anomaly_class_reason"] = reasons

    return out


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    # Sibling import shim.
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402
    from qc_rules import apply_qc_rules  # noqa: E402
    from spatial_analysis import (  # noqa: E402
        apply_spatial_analysis,
    )
    from temporal_detector import apply_temporal_detector  # noqa: E402

    print("=" * 70)
    print("SkyGuard AI - STEP 17: Anomaly Classification (demo)")
    print("=" * 70)

    # 1. Load test data.
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])
    print(f"\nLoaded observations: {len(obs)} rows")

    # 2-3. Build features + QC.
    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()
    print(f"QC flags computed: {len(qc)} rows")

    # 4. Spatial analysis (suppress neighbour graph print).
    metadata_path = "data/station_metadata.csv"
    spatial = None
    if os.path.exists(metadata_path):
        metadata = pd.read_csv(metadata_path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            spatial = apply_spatial_analysis(obs, metadata)
        spatial_cols = ["station_id", "timestamp"] + [
            c for c in spatial.columns if c.startswith("spatial_")
        ]
        spatial = spatial[spatial_cols].copy()
        print(f"Spatial flags computed: {len(spatial)} rows")
    else:
        print("[SKIP] station_metadata.csv not found; spatial skipped")

    # 5. Temporal detector.
    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()
    print(f"Temporal flags computed: {len(temporal)} rows")

    # 6. Load IF predictions.
    if_path = "data/isolation_forest_predictions.csv"
    if_df = pd.read_csv(if_path)
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()
    print(f"IF predictions loaded: {len(if_df)} rows")

    # 7. Join all sources on (station_id, timestamp).
    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    if spatial is not None:
        joined = joined.merge(
            spatial, on=["station_id", "timestamp"], how="left"
        )
    joined = joined.merge(
        temporal, on=["station_id", "timestamp"], how="left"
    )
    print(f"Joined DataFrame: {len(joined)} rows, {len(joined.columns)} cols")

    # 8. Run classifier.
    result = classify_anomalies(joined)

    # 9. Print diagnostics.
    print(f"\nTotal rows: {len(result)}")

    print(f"\nDistribution of anomaly_class:")
    print(result["anomaly_class"].value_counts().to_string())

    print(f"\nDistribution of anomaly_class_confidence:")
    print(result["anomaly_class_confidence"].value_counts().to_string())

    # Cross-check vs is_anomaly.
    if "is_anomaly" in result.columns:
        print(f"\n--- Cross-check vs is_anomaly ---")
        print(
            f"  {'anomaly_class':<35s}  {'total':>6s}  "
            f"{'anomaly':>8s}  {'normal':>8s}  {'precision':>10s}"
        )
        print("  " + "-" * 75)
        for cls, g in result.groupby("anomaly_class"):
            n_total = len(g)
            n_anom = int((g["is_anomaly"] == 1).sum())
            n_norm = int((g["is_anomaly"] == 0).sum())
            prec = n_anom / n_total if n_total > 0 else 0.0
            print(
                f"  {cls:<35s}  {n_total:>6d}  "
                f"{n_anom:>8d}  {n_norm:>8d}  {prec:>9.1%}"
            )

    # Top 5 rows with confidence == "high".
    print(f"\n--- Top 5 rows with confidence == 'high' ---")
    high = result[result["anomaly_class_confidence"] == "high"].head(5)
    if high.empty:
        print("  (none)")
    else:
        cols_show = [
            "timestamp", "station_id", "anomaly_class",
            "anomaly_class_reason",
        ]
        for line in high[cols_show].to_string(
            index=False, max_colwidth=80
        ).splitlines():
            print("  " + line)

    # Rows where anomaly_class == "Unclassified".
    print(f"\n--- Rows classified as 'Unclassified' ---")
    unclass = result[result["anomaly_class"] == CLASS_UNCLASSIFIED]
    print(f"  Total: {len(unclass)}")
    if len(unclass) > 0:
        cols_show = [
            "timestamp", "station_id", "anomaly_class_reason",
        ]
        for line in unclass[cols_show].head(10).to_string(
            index=False, max_colwidth=80
        ).splitlines():
            print("  " + line)