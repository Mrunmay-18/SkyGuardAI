"""
src/explainer.py
SkyGuard AI - Natural-Language Explanation Layer.

Generates human-readable anomaly explanations from the evidence
produced by the 4 evidence sources (Isolation Forest, QC rules,
spatial consistency, temporal detector). Uses natural-language
phrasing instead of verbatim reason strings, preserving numeric
detail in parentheses when available.

Public interface:
    explain_row(row)       — returns a multi-line text explanation
    explain_dataframe(df)  — adds an "explanation" column to df

Does NOT modify any existing file. Uses pandas and numpy only.
"""

import os
import sys

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Recommendation mapping (unchanged by reason-phrasing revision)
# ----------------------------------------------------------------------
RECOMMENDATION_MAP = {
    "Temperature Spike": (
        "Inspect the temperature sensor and verify the reading."
    ),
    "Temperature Drop": (
        "Inspect the temperature sensor and verify the reading."
    ),
    "Frozen Sensor": (
        "Inspect the sensor for a stuck value and check sensor health."
    ),
    "Calibration Drift": (
        "Inspect sensor calibration and compare with a reference "
        "measurement."
    ),
    "Communication Failure": (
        "Check station communication, connectivity, and data "
        "transmission."
    ),
    "Multivariate Inconsistency": (
        "Inspect the affected measurements and verify sensor "
        "consistency."
    ),
    "Likely Sensor/Data Anomaly": (
        "Inspect the station data and sensor readings."
    ),
    "Possible Genuine Weather Event": (
        "Cross-check nearby stations and relevant official weather or "
        "hazard information."
    ),
    "Unclassified": (
        "Further investigation is required because the available "
        "evidence does not support a specific anomaly classification."
    ),
    "Normal": (
        "No action required."
    ),
}


# ----------------------------------------------------------------------
# Safe access helpers
# ----------------------------------------------------------------------
def _safe_int(row, col):
    """Return int value; missing or NaN → 0."""
    if col not in row.index:
        return 0
    val = row[col]
    if pd.isna(val):
        return 0
    return int(val)


def _safe_float(row, col):
    """Return float value; missing or NaN → NaN."""
    if col not in row.index:
        return np.nan
    val = row[col]
    if pd.isna(val):
        return np.nan
    return float(val)


def _safe_str(row, col):
    """Return str value; missing or NaN → ''."""
    if col not in row.index:
        return ""
    val = row[col]
    if pd.isna(val):
        return ""
    return str(val)


# ----------------------------------------------------------------------
# Numeric-detail parsers (extract numbers from raw reason strings)
# ----------------------------------------------------------------------
def _parse_d_value(reason: str) -> str | None:
    """Extract 'd=X.XX' from a QC temporal reason like 'd=5.920'."""
    if not reason or "d=" not in reason:
        return None
    try:
        d_part = reason.split("d=")[1].split(",")[0].split(")")[0]
        d_val = float(d_part)
        return f"d={d_val:.2f}"
    except (ValueError, IndexError):
        return None


def _parse_consecutive_samples(reason: str) -> str | None:
    """Extract 'N consecutive samples' from a persistence or temporal reason."""
    if not reason:
        return None
    if "consecutive samples" not in reason:
        return None
    try:
        before = reason.split("consecutive samples")[0]
        parts = before.split()
        for part in reversed(parts):
            num = part.strip(".,;()")
            if num.isdigit():
                return f"{num} consecutive samples"
        for part in reversed(parts):
            try:
                num = int(part.strip(".,;()"))
                return f"{num} consecutive samples"
            except ValueError:
                continue
    except (ValueError, IndexError):
        pass
    return None


def _parse_internal_detail(reason: str) -> str | None:
    """Extract descriptive detail from a QC internal reason."""
    if not reason:
        return None
    detail = reason.strip()
    if not detail:
        return None
    for sep in ["; ", ", "]:
        if sep in detail:
            detail = detail.split(sep)[0]
    if len(detail) > 60:
        detail = detail[:57] + "..."
    return detail


def _parse_range_detail(reason: str) -> str | None:
    """Extract parameter and range from a QC range reason."""
    if not reason:
        return None
    detail = reason.strip()
    if not detail:
        return None
    if "; " in detail:
        detail = detail.split("; ")[0]
    if len(detail) > 80:
        detail = detail[:77] + "..."
    return detail


def _parse_gap_detail(reason: str) -> str | None:
    """Extract sample count and duration from a QC gap reason."""
    if not reason:
        return None
    parts = []
    if " samples" in reason:
        try:
            before_samples = reason.split(" samples")[0]
            num_part = before_samples.split()[-1]
            num = int(num_part)
            parts.append(f"{num} samples")
        except (ValueError, IndexError):
            pass
    if "minutes" in reason or "minute" in reason:
        try:
            before_min = reason.split("minute")[0]
            num_part = before_min.split()[-1].strip("()")
            minutes = int(float(num_part))
            if minutes >= 60 and minutes % 60 == 0:
                parts.append(f"{minutes // 60} hours")
            elif minutes >= 60:
                parts.append(f"{minutes / 60:.1f} hours")
            else:
                parts.append(f"{minutes} minutes")
        except (ValueError, IndexError):
            pass
    if parts:
        return ", ".join(parts)
    return None


def _max_abs_z(row) -> tuple:
    """Return the max |temporal_z_*| across 3 windows, NaN-safe."""
    best = None
    best_col = None
    for col in ["temporal_z_4", "temporal_z_8", "temporal_z_16"]:
        z = _safe_float(row, col)
        if not np.isnan(z):
            abs_z = abs(z)
            if best is None or abs_z > best:
                best = abs_z
                best_col = col
    if best is not None:
        return best, best_col
    return None, None


# ----------------------------------------------------------------------
# Natural-language evidence bullet builders
# ----------------------------------------------------------------------
def _build_evidence_bullets(row) -> list:
    """
    Build a list of natural-language evidence bullets for a row.

    Uses natural-language phrasing instead of verbatim reason strings.
    Numeric detail is appended in parentheses when available.
    Implements the 'no duplicate bullets' rule: overlapping reasons
    from different sources are collapsed if they produce identical text.
    """
    bullets = []

    # --- Isolation Forest ---
    if _safe_int(row, "predicted_anomaly") == 1:
        score = _safe_float(row, "anomaly_score")
        if not np.isnan(score):
            bullets.append(
                f"Isolation Forest flagged this observation as "
                f"anomalous (score={score:.3f})."
            )
        else:
            bullets.append(
                "Isolation Forest flagged this observation as anomalous."
            )

    # --- QC rules (each flag gets a natural-language bullet) ---
    if _safe_int(row, "qc_temporal_flag") == 1:
        reason = _safe_str(row, "qc_temporal_reason")
        d_val = _parse_d_value(reason)
        if d_val:
            bullets.append(
                f"QC temporal check flagged a large temperature "
                f"change ({d_val})."
            )
        else:
            bullets.append(
                "QC temporal check flagged a large temperature change."
            )

    if _safe_int(row, "qc_persistence_flag") == 1:
        reason = _safe_str(row, "qc_persistence_reason")
        consec = _parse_consecutive_samples(reason)
        if consec:
            bullets.append(
                f"QC persistence check detected a stuck value "
                f"({consec})."
            )
        else:
            bullets.append(
                "QC persistence check detected a stuck value."
            )

    if _safe_int(row, "qc_internal_flag") == 1:
        reason = _safe_str(row, "qc_internal_reason")
        detail = _parse_internal_detail(reason)
        if detail:
            bullets.append(
                f"QC internal consistency check flagged an "
                f"inconsistent reading ({detail})."
            )
        else:
            bullets.append(
                "QC internal consistency check flagged an inconsistent reading."
            )

    if _safe_int(row, "qc_range_flag") == 1:
        reason = _safe_str(row, "qc_range_reason")
        detail = _parse_range_detail(reason)
        if detail:
            bullets.append(
                f"QC range check flagged a value outside operational "
                f"bounds ({detail})."
            )
        else:
            bullets.append(
                "QC range check flagged a value outside operational bounds."
            )

    if _safe_int(row, "qc_gap_flag") == 1:
        reason = _safe_str(row, "qc_gap_reason")
        detail = _parse_gap_detail(reason)
        if detail:
            bullets.append(
                f"QC gap check detected a missing-observation gap "
                f"({detail})."
            )
        else:
            bullets.append(
                "QC gap check detected a missing-observation gap."
            )

    # --- Temporal detector ---
    if _safe_int(row, "temporal_level1_flag") == 1:
        max_z, z_col = _max_abs_z(row)
        if max_z is not None:
            bullets.append(
                f"Temporal detector flagged a sudden temperature "
                f"change ({z_col}={max_z:.2f})."
            )
        else:
            bullets.append(
                "Temporal detector flagged a sudden temperature change."
            )

    if _safe_int(row, "temporal_level2_flag") == 1:
        reason = _safe_str(row, "temporal_reason")
        consec = _parse_consecutive_samples(reason)
        if consec:
            bullets.append(
                f"Temporal detector flagged sustained temperature "
                f"deviation (above threshold for {consec})."
            )
        else:
            bullets.append(
                "Temporal detector flagged sustained temperature deviation."
            )

    # --- Spatial consistency ---
    if _safe_int(row, "spatial_isolated_flag") == 1:
        bullets.append(
            "Station reading differs from nearby-station evidence."
        )

    if _safe_int(row, "spatial_common_event_flag") == 1:
        bullets.append(
            "Nearby stations show a common change — possible "
            "genuine weather event."
        )

    # --- No-duplicate-bullets rule ---
    seen = set()
    unique_bullets = []
    for b in bullets:
        if b not in seen:
            seen.add(b)
            unique_bullets.append(b)

    # --- Insufficient-evidence fallback ---
    if not unique_bullets:
        any_evidence = (
            _safe_int(row, "predicted_anomaly") == 1
            or _safe_int(row, "qc_any_flag") == 1
            or _safe_int(row, "spatial_isolated_flag") == 1
            or _safe_int(row, "temporal_predicted_anomaly") == 1
            or _safe_int(row, "fused_any_flag") == 1
        )
        if any_evidence:
            unique_bullets.append(
                "Anomaly evidence detected, but available signals "
                "are insufficient to produce detailed explanation."
            )
        else:
            unique_bullets.append(
                "No anomaly evidence detected from any source."
            )

    return unique_bullets


# ----------------------------------------------------------------------
# Recommendation helper (unchanged by reason-phrasing revision)
# ----------------------------------------------------------------------
def _get_recommendation(row) -> str:
    """Map anomaly_class to a recommended action."""
    cls = _safe_str(row, "anomaly_class")
    if cls in RECOMMENDATION_MAP:
        return RECOMMENDATION_MAP[cls]
    if _safe_int(row, "predicted_anomaly") == 1 or \
       _safe_int(row, "qc_any_flag") == 1 or \
       _safe_int(row, "temporal_predicted_anomaly") == 1 or \
       _safe_int(row, "spatial_isolated_flag") == 1:
        return "Review manually with all available evidence."
    return "No action required."


# ----------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------
def explain_row(row: pd.Series) -> str:
    """
    Generate a multi-line human-readable explanation for a single row.

    Parameters
    ----------
    row : pd.Series
        A single row from a joined DataFrame with evidence-source
        outputs. Missing columns are tolerated — treated as absent.

    Returns
    -------
    str
        Multi-line text explanation with section headers.
    """
    lines = []
    lines.append("=== Anomaly Explanation ===")

    station = _safe_str(row, "station_id") or "N/A"
    timestamp = _safe_str(row, "timestamp") or "N/A"
    lines.append(f"Station: {station}")
    lines.append(f"Timestamp: {timestamp}")

    cls = _safe_str(row, "anomaly_class")
    if cls:
        lines.append(f"Anomaly Class: {cls}")

    conf = _safe_int(row, "anomaly_confidence")
    if conf > 0 or "anomaly_confidence" in row.index:
        lines.append(f"Confidence: {conf}/100")

    sev = _safe_str(row, "severity")
    if sev:
        lines.append(f"Severity: {sev}")

    lines.append("")
    lines.append("Reasons:")
    bullets = _build_evidence_bullets(row)
    for b in bullets:
        lines.append(f"  - {b}")

    lines.append("")
    lines.append("Recommendation:")
    lines.append(f"  {_get_recommendation(row)}")

    return "\n".join(lines)


def explain_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'explanation' column to a DataFrame of observations.

    Parameters
    ----------
    df : pd.DataFrame
        Joined observations with evidence-source outputs. Missing
        columns are tolerated.

    Returns
    -------
    pd.DataFrame
        Copy of df with ADDED column 'explanation' (str).
        The input is NOT mutated.
    """
    out = df.copy()
    explanations = []
    for i in range(len(out)):
        explanations.append(explain_row(out.iloc[i]))
    out["explanation"] = explanations
    return out


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402
    from qc_rules import apply_qc_rules  # noqa: E402
    from spatial_analysis import apply_spatial_analysis  # noqa: E402
    from temporal_detector import apply_temporal_detector  # noqa: E402
    from anomaly_classifier import classify_anomalies  # noqa: E402
    from scoring import score_anomalies  # noqa: E402

    print("=" * 70)
    print("SkyGuard AI - Explainer Demo")
    print("=" * 70)

    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])

    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()

    metadata = pd.read_csv("data/station_metadata.csv")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spatial = apply_spatial_analysis(obs, metadata)
    spatial_cols = ["station_id", "timestamp"] + [
        c for c in spatial.columns if c.startswith("spatial_")
    ]
    spatial = spatial[spatial_cols].copy()

    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()

    if_df = pd.read_csv("data/isolation_forest_predictions.csv")
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()

    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(spatial, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(temporal, on=["station_id", "timestamp"], how="left")

    classified = classify_anomalies(joined)
    scored = score_anomalies(classified)
    explained = explain_dataframe(scored)

    print(f"\nExplained {len(explained)} rows\n")

    # ------------------------------------------------------------------
    # Priority-based example selection.
    #
    # Goal: guarantee the demo showcases the most interesting rows,
    # not just whichever happens to be first in file order.
    #
    # Priority:
    #   1. Critical severity row
    #   2. High severity row
    #   3. Frozen Sensor (QC catches what IF misses)
    #   4. Possible Genuine Weather Event (spatial counter-evidence)
    #   5. Normal row (baseline)
    # Then fill remaining slots with any anomaly rows not yet chosen.
    # ------------------------------------------------------------------
    chosen = []           # list of (label, index) tuples
    chosen_ids = set()    # set of indices already chosen

    def _try_add(mask, label):
        """Add the first matching row for `mask` if not already chosen."""
        sub = explained[mask]
        if len(sub) > 0:
            idx = sub.index[0]
            if idx not in chosen_ids:
                chosen.append((label, idx))
                chosen_ids.add(idx)

    # Priority picks (each may add zero or one row).
    _try_add(explained["severity"] == "Critical", "Critical severity")
    _try_add(explained["severity"] == "High", "High severity")
    _try_add(
        explained["anomaly_class"] == "Frozen Sensor",
        "Frozen Sensor (QC catches what IF misses)",
    )
    _try_add(
        explained["anomaly_class"] == "Possible Genuine Weather Event",
        "Possible Genuine Weather Event (spatial counter-evidence)",
    )
    _try_add(explained["anomaly_class"] == "Normal", "Normal baseline")

    # Fill remaining slots with anomaly rows not yet chosen.
    if len(chosen) < 5:
        for idx in explained.index:
            if idx in chosen_ids:
                continue
            if explained.loc[idx, "anomaly_class"] != "Normal":
                chosen.append(("Anomaly", idx))
                chosen_ids.add(idx)
                if len(chosen) >= 5:
                    break

    # If we still have fewer than 5 (small dataset edge case),
    # fill with any remaining Normal rows.
    if len(chosen) < 5:
        for idx in explained.index:
            if idx in chosen_ids:
                continue
            chosen.append(("Normal", idx))
            chosen_ids.add(idx)
            if len(chosen) >= 5:
                break

    # Print at most 5 examples.
    for i, (label, idx) in enumerate(chosen[:5], start=1):
        print(f"--- Example {i}: {label} ---")
        print(explain_row(explained.loc[idx]))
        print()