"""
src/backend_output.py
SkyGuard AI — STEP 22: Final backend output.

Converts the final outputs of Steps 17–21 into a clean, frontend-friendly
JSON structure (one object per detected anomaly). No ML here — pure
formatting and joining.

Reads:
    - scored DataFrame (from classify_anomalies + score_anomalies + explain_dataframe)
    - sensor health DataFrame (from calculate_sensor_health)

Writes:
    - outputs/alerts.json  (list of dicts, one per anomaly)
"""

import json
import os
import sys

import pandas as pd


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
OUTPUT_DIR = "outputs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "alerts.json")

# Sensor health normalization (from the plan).
HEALTH_MAP = {
    "Healthy": "healthy",
    "Watch": "watch",
    "At Risk": "at_risk",
}

# Columns that must exist in the scored DataFrame for backend output.
REQUIRED_COLUMNS = [
    "station_id",
    "timestamp",
    "temperature",
    "pressure",
    "humidity",
    "anomaly_class",
    "anomaly_confidence",
    "severity",
    "explanation",
]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _safe_float(value):
    """Return float or None if not convertible."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    """Return int or None if not convertible."""
    try:
        if pd.isna(value):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _row_is_anomaly(row) -> bool:
    """
    A row is an anomaly if the fused evidence layer says so.

    Uses fused_any_flag (Step 17 output), which requires
    corroborating evidence from multiple detectors. Falls back
    to the raw union ONLY if fused_any_flag is missing.
    """
    # Preferred: use the fusion decision.
    if "fused_any_flag" in row.index:
        try:
            return int(row["fused_any_flag"]) == 1
        except (TypeError, ValueError):
            pass

    # Fallback: raw union (only if fusion output is missing).
    flags = [
        "predicted_anomaly",
        "qc_any_flag",
        "temporal_predicted_anomaly",
        "spatial_any_flag",
        "spatial_isolated_flag",
    ]
    for f in flags:
        if f in row.index:
            try:
                if int(row[f]) == 1:
                    return True
            except (TypeError, ValueError):
                pass
    return False


def _build_reasons(row) -> list:
    """
    Extract only the actual reasons from the Step 19 explanation.

    The explainer produces a structured block like:

        === Anomaly Explanation ===
        Station: AWS_05
        ...
        Reasons:
        - <reason 1>
        - <reason 2>
        Recommendation:
        <recommendation text>

    We keep ONLY the lines between 'Reasons:' and 'Recommendation:'.
    Station, timestamp, confidence, severity, and recommendation
    already have dedicated JSON fields, so they must not appear here.
    """
    raw = row.get("explanation", "")

    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []

    text = str(raw).strip()

    if not text:
        return []

    lines = text.splitlines()

    reasons = []
    in_reasons = False

    for line in lines:
        line = line.strip()

        if line.lower() == "reasons:":
            in_reasons = True
            continue

        if line.lower() == "recommendation:":
            break

        if in_reasons and line:
            cleaned = line.lstrip("-•\t ").strip()
            if cleaned:
                reasons.append(cleaned)

    return reasons
# ----------------------------------------------------------------------
# Corrected value estimation (self-healing)
# ----------------------------------------------------------------------
def _compute_corrected_values(
    row,
    meta: "pd.DataFrame",
    obs_df: "pd.DataFrame",
) -> dict:
    """
    Estimate corrected T/P/H for an anomalous reading using the median
    of neighbouring stations at the same timestamp.

    Returns a dict with:
        corrected_temperature, corrected_pressure, corrected_humidity,
        correction_confidence (0-100 or None),
        correction_basis (string describing how it was computed)

    If neighbours cannot be determined (missing metadata, no valid
    neighbour reading at this timestamp), returns empty values with a
    basis note explaining why.
    """
    empty = {
        "corrected_temperature": None,
        "corrected_pressure": None,
        "corrected_humidity": None,
        "correction_confidence": None,
        "correction_basis": "not available",
    }

    station_id = row.get("station_id")
    ts = row.get("timestamp")
    if station_id is None or ts is None:
        return empty

    # Find neighbours (all other stations within 100 km, simple fallback).
    if station_id not in meta["station_id"].values:
        return empty
    me = meta[meta["station_id"] == station_id].iloc[0]
    others = meta[meta["station_id"] != station_id].copy()

    # Haversine distance (km)
    import numpy as np
    R = 6371.0088
    lat1, lon1 = np.radians(me["latitude"]), np.radians(me["longitude"])
    lat2 = np.radians(others["latitude"].to_numpy())
    lon2 = np.radians(others["longitude"].to_numpy())
    dphi = lat2 - lat1
    dlam = lon2 - lon1
    a = np.sin(dphi / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlam / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    others["distance_km"] = R * c

    # Keep 2 nearest neighbours within 100 km.
    neighbours = others[others["distance_km"] <= 100.0].nsmallest(2, "distance_km")
    if len(neighbours) == 0:
        return empty

    # Find their readings at the same timestamp.
    ts_str = str(ts)
    neighbour_ids = neighbours["station_id"].tolist()
    same_ts = obs_df[
        (obs_df["timestamp"].astype(str) == ts_str)
        & (obs_df["station_id"].isin(neighbour_ids))
    ]

    if len(same_ts) == 0:
        return {
            **empty,
            "correction_basis": "no neighbour reading at this timestamp",
        }

    t_med = same_ts["temperature"].median() if same_ts["temperature"].notna().any() else None
    p_med = same_ts["pressure"].median() if same_ts["pressure"].notna().any() else None
    h_med = same_ts["humidity"].median() if same_ts["humidity"].notna().any() else None

    # Confidence: higher when neighbours agree tightly.
    # Uses 1 - (std / mean) heuristic, clamped to 50-95.
    def _agreement_conf(series):
        if series.dropna().empty or len(series.dropna()) < 2:
            return 70  # only one neighbour → moderate
        vals = series.dropna()
        if vals.mean() == 0:
            return 70
        spread = float(vals.std() / abs(vals.mean()))
        conf = max(50, min(95, int(95 - spread * 500)))
        return conf

    conf_t = _agreement_conf(same_ts["temperature"])
    conf_p = _agreement_conf(same_ts["pressure"])
    conf_h = _agreement_conf(same_ts["humidity"])
    correction_confidence = int((conf_t + conf_p + conf_h) / 3)

    neighbour_str = ", ".join(neighbour_ids[:2])
    return {
        "corrected_temperature": round(float(t_med), 2) if t_med is not None else None,
        "corrected_pressure": round(float(p_med), 2) if p_med is not None else None,
        "corrected_humidity": round(float(h_med), 2) if h_med is not None else None,
        "correction_confidence": correction_confidence,
        "correction_basis": f"median of {len(same_ts)} neighbouring station(s) ({neighbour_str})",
    }

def _compute_priority(severity: str, confidence, spatial_isolated: bool) -> str:
    """
    Derive operational priority from severity, confidence, and spatial isolation.

    P1 — urgent: High severity with strong evidence
    P2 — important: Medium severity or moderate confidence
    P3 — routine: Low severity or low confidence
    """
    sev = str(severity or "").strip().lower()
    try:
        conf = int(confidence) if confidence is not None else 0
    except (TypeError, ValueError):
        conf = 0

    if sev == "high" and conf >= 80:
        return "P1"
    if sev == "high" and conf >= 60 and spatial_isolated:
        return "P1"
    if sev == "low" or conf < 50:
        return "P3"
    return "P2"

def _compute_evidence_breakdown(row) -> dict:
    """
    Extract per-source evidence from a scored row.

    Returns a dict with:
        evidence_breakdown: per-source flags + key numeric details
        decision_basis: human-readable count of agreeing sources
        counter_evidence: text describing counter-evidence (spatial common event)
    """
    def _flag(col):
        try:
            return bool(int(row.get(col, 0) or 0))
        except (TypeError, ValueError):
            return False

    def _num(col):
        try:
            v = row.get(col)
            if v is None:
                return None
            return round(float(v), 4)
        except (TypeError, ValueError):
            return None

    if_fired = _flag("predicted_anomaly")
    qc_fired = _flag("qc_any_flag")
    temporal_fired = _flag("temporal_predicted_anomaly")
    spatial_isolated = _flag("spatial_isolated_flag")
    spatial_common = _flag("spatial_common_event_flag")

    breakdown = {
        "ml_if": {
            "fired": if_fired,
            "score": _num("anomaly_score") if if_fired else None,
            "weight": 1.0,
        },
        "qc_any": {
            "fired": qc_fired,
            "count": int(row.get("qc_flag_count", 0) or 0),
            "weight": 0.7,
        },
        "temporal": {
            "fired": temporal_fired,
            "z_4": _num("temporal_z_4") if temporal_fired else None,
            "weight": 1.0,
        },
        "spatial": {
            "fired": spatial_isolated,
            "isolated": spatial_isolated,
            "weight": 1.2,
        },
    }

    fired_sources = [name for name, d in breakdown.items() if d["fired"]]
    n_fired = len(fired_sources)
    n_possible = 4

    if n_fired == 0:
        decision_basis = "no sources fired"
    else:
        decision_basis = f"{n_fired} of {n_possible} sources agree: {', '.join(fired_sources)}"

    if spatial_common:
        counter_evidence = "spatial common event detected (regional weather pattern)"
    else:
        counter_evidence = "none"

    return {
        "evidence_breakdown": breakdown,
        "decision_basis": decision_basis,
        "counter_evidence": counter_evidence,
    }
def _compute_counter_reasoning(row) -> dict:
    """
    Explicitly reason about whether this is a sensor fault or a genuine
    weather event, using available spatial counter-evidence.

    Returns:
        verdict: "sensor_fault" | "possible_weather_event" | "inconclusive"
        reason:  human-readable sentence
    """
    spatial_common = bool(int(row.get("spatial_common_event_flag", 0) or 0))
    spatial_isolated = bool(int(row.get("spatial_isolated_flag", 0) or 0))

    spatial_common = bool(int(row.get("spatial_common_event_flag", 0) or 0))
    spatial_isolated = bool(int(row.get("spatial_isolated_flag", 0) or 0))

    # Reliability of the spatial evidence.
    try:
        n_neigh = int(row.get("spatial_neighbours_n", 0) or 0)
    except (TypeError, ValueError):
        n_neigh = 0

    if n_neigh >= 2:
        reliability = "high"
        reliability_note = f"{n_neigh} nearby stations used for spatial comparison."
    elif n_neigh == 1:
        reliability = "medium"
        reliability_note = "Only 1 neighbor available — spatial evidence weaker."
    else:
        reliability = "low"
        reliability_note = "No neighbors available — spatial evidence not usable."

    if spatial_common:
        return {
            "verdict": "possible_weather_event",
            "reason": (
                "Neighboring stations showed a common change — "
                "consistent with a regional weather event."
            ),
            "reliability": reliability,
            "reliability_note": reliability_note,
        }

    if spatial_isolated:
        return {
            "verdict": "sensor_fault",
            "reason": (
                "This station deviated from its neighbors while "
                "neighbors remained consistent — isolated sensor "
                "signature, not regional weather."
            ),
            "reliability": reliability,
            "reliability_note": reliability_note,
        }

    return {
        "verdict": "inconclusive",
        "reason": (
            "No spatial counter-evidence available (neighbors "
            "insufficient or timestamp mismatch)."
        ),
        "reliability": reliability,
        "reliability_note": reliability_note,
    }
def _compute_trust_score(row, evidence_breakdown: dict) -> int:
    """
    Compute a system-level trust score (0-100).

    Higher when:
      - Multiple independent sources agree
      - Confidence is high
      - Counter-evidence is absent
      - Spatial isolation supports the fault hypothesis
    """
    n_fired = sum(1 for d in evidence_breakdown.values() if d.get("fired"))
    try:
        conf = int(row.get("anomaly_confidence") or 0)
    except (TypeError, ValueError):
        conf = 0

    score = 0
    score += n_fired * 15               # up to 75 from evidence count
    score += conf * 0.2                 # up to 20 from confidence

    if bool(int(row.get("spatial_common_event_flag", 0) or 0)):
        score -= 30                     # penalty for counter-evidence
    if bool(int(row.get("spatial_isolated_flag", 0) or 0)):
        score += 5                      # small bonus for isolation

    return max(0, min(100, int(score)))
def _compute_event_class(row) -> str:
    """
    Classify the alert as either a sensor fault or a genuine weather event
    based on spatial counter-evidence.
    """
    if bool(int(row.get("spatial_common_event_flag", 0) or 0)):
        return "weather"
    return "sensor_fault"

def _compute_physical_reasoning(row) -> str:
    """
    Produce a physics-based sentence describing why this specific
    anomaly type is anomalous — not a generic label.

    Each anomaly type has a different physical signature. This function
    produces type-specific reasoning so the alert does not look the same
    for a frozen sensor and a temperature spike.
    """
    anomaly_class = str(row.get("anomaly_class", "")).strip()

    # Extract useful values for richer sentences.
    def _safe(val, default=None):
        try:
            if val is None:
                return default
            return float(val)
        except (TypeError, ValueError):
            return default

    temp = _safe(row.get("temperature"))
    press = _safe(row.get("pressure"))
    humid = _safe(row.get("humidity"))
    d_temp = _safe(row.get("d_temperature"))
    z4 = _safe(row.get("temporal_z_4"))
    qc_count = _safe(row.get("qc_flag_count"), 0)

    # --- Anomaly-specific reasoning ---

    if anomaly_class == "Frozen Sensor":
        return (
            "Reading has remained constant across many consecutive samples. "
            "Natural atmospheric parameters cannot stay perfectly constant "
            "over time — this is consistent with a stuck or frozen sensor."
        )

    if anomaly_class == "Temperature Spike":
        if d_temp is not None and abs(d_temp) > 0.01:
            dt_str = f"{abs(d_temp):.1f}°C"
        else:
            dt_str = "a large amount"
        return (
            f"Temperature changed by {dt_str} within one reading interval. "
            "Natural atmospheric temperature cannot change that fast — "
            "sensor spike signature."
        )

    if anomaly_class == "Temperature Drop":
        if d_temp is not None and abs(d_temp) > 0.01:
            dt_str = f"{abs(d_temp):.1f}°C"
        else:
            dt_str = "a large amount"
        return (
            f"Temperature dropped by {dt_str} within one interval while "
            "pressure and humidity did not show a corresponding change — "
            "inconsistent with a physical weather transition."
        )

    if anomaly_class == "Multivariate Inconsistency":
        return (
            "Temperature changed but humidity and pressure did not respond. "
            "In real atmospheric transitions, temperature, pressure and "
            "humidity change together — this violates physical coupling."
        )

    if anomaly_class == "Power Failure":
        return (
            "All three parameters (temperature, pressure, humidity) "
            "collapsed to zero simultaneously. No atmospheric state "
            "produces this combination — sensor or power failure."
        )

    if anomaly_class == "Calibration Drift":
        return (
            "Gradual sustained shift observed over many samples. "
            "Neither sudden (spike) nor isolated (spatial) — consistent "
            "with slow sensor calibration drift."
        )

    if anomaly_class == "Communication Failure":
        return (
            "Timestamp gap detected in the data stream. No observations "
            "were recorded during this interval — communication or power "
            "loss signature."
        )

    # Fallback: generic
    parts = []
    if z4 is not None and abs(z4) > 2:
        parts.append(f"temporal z-score {z4:+.1f}")
    if qc_count:
        parts.append(f"{int(qc_count)} QC rule(s) fired")
    detail = ", ".join(parts) if parts else "multi-source evidence"
    return f"Anomaly detected by {detail}."
def _compute_multivariate_analysis(row) -> dict:
    """
    Check whether the direction and magnitude of T / P / RH changes
    are physically coupled (as expected in real weather) or decoupled
    (which suggests a sensor fault).

    Returns:
        verdict: "physically_plausible" | "physically_implausible" | "insufficient_data"
        reason:  human-readable sentence
        details: numeric summary of changes
    """
    def _safe(val, default=None):
        try:
            if val is None:
                return default
            v = float(val)
            if v != v:  # NaN check
                return default
            return v
        except (TypeError, ValueError):
            return default

    d_t = _safe(row.get("d_temperature"))
    d_p = _safe(row.get("d_pressure"))
    d_h = _safe(row.get("d_humidity"))

    details = {
        "temperature_change": d_t,
        "pressure_change": d_p,
        "humidity_change": d_h,
    }

    if d_t is None or d_h is None:
        return {
            "verdict": "insufficient_data",
            "reason": "Multi-variable deltas not available for this reading.",
            "details": details,
        }

    # If the raw reading is all zeros, this is a total collapse.
    raw_t = _safe(row.get("temperature"))
    raw_p = _safe(row.get("pressure"))
    raw_h = _safe(row.get("humidity"))
    if raw_t == 0 and raw_p == 0 and raw_h == 0:
        return {
            "verdict": "total_collapse",
            "reason": (
                "All three parameters are exactly zero. "
                "No atmospheric state produces this - power or sensor failure."
            ),
            "details": details,
        }

        
    # Detect total sensor/power collapse (all parameters crashed together).
    # A collapse is NOT a coupling violation — it's a system failure.
    extreme_threshold = 20.0
    all_extreme = (
        d_t is not None and abs(d_t) >= extreme_threshold and
        d_h is not None and abs(d_h) >= extreme_threshold
    )
    if all_extreme:
        return {
            "verdict": "total_collapse",
            "reason": (
                f"All parameters collapsed simultaneously "
                f"(T change {d_t:+.1f}, humidity change {d_h:+.1f}). "
                "No atmospheric process produces this combination — "
                "sensor or power failure signature."
            ),
            "details": details,
        }
    # Physical expectation: T and RH move in opposite directions.
    # T up -> RH down (heating dries air).
    # T down -> RH up (cooling moistens air).
    if abs(d_t) < 0.5:
        return {
            "verdict": "physically_plausible",
            "reason": (
                f"Temperature change ({d_t:+.2f} C) is within normal fluctuation. "
                "No coupling violation detected."
            ),
            "details": details,
        }

    expected_rh_direction = "up" if d_t < 0 else "down"

    coupling_ok = (
        (expected_rh_direction == "up" and d_h > 0.5) or
        (expected_rh_direction == "down" and d_h < -0.5)
    )

    if coupling_ok:
        return {
            "verdict": "physically_plausible",
            "reason": (
                f"Temperature moved {d_t:+.1f} C with humidity {d_h:+.1f}% "
                f"(expected {expected_rh_direction}). Coupling consistent with "
                "physical atmospheric behavior."
            ),
            "details": details,
        }

    return {
        "verdict": "physically_implausible",
        "reason": (
            f"Temperature moved {d_t:+.1f} C while humidity changed only "
            f"{d_h:+.1f}% (expected {expected_rh_direction}). "
            "This violates physical coupling - stronger evidence of sensor fault."
        ),
        "details": details,
    }


def _compute_genuine_weather_verdict(row, multivariate: dict) -> dict:
    """
    Produce a final verdict: is this a genuine weather event or a sensor fault?

    Combines three signals:
      1. Spatial common event (neighbors also changed)
      2. Multivariate coupling (physics check)
      3. Anomaly type classification

    Returns:
        genuine_weather_event: bool
        weather_verdict_reason: str
    """
    spatial_common = bool(int(row.get("spatial_common_event_flag", 0) or 0))
    anomaly_class = str(row.get("anomaly_class", "")).strip()
    mv_verdict = multivariate.get("verdict", "insufficient_data")

    # Rule 1: If neighbors changed together -> regional event
    if spatial_common:
        return {
            "genuine_weather_event": True,
            "weather_verdict_reason": (
                "Neighboring stations showed a common change - "
                "this is a regional weather pattern, not an isolated sensor fault."
            ),
        }

    # Rule 2: If the anomaly is multivariate-inconsistent -> definitely fault
    if anomaly_class == "Multivariate Inconsistency":
        return {
            "genuine_weather_event": False,
            "weather_verdict_reason": (
                "Temperature, pressure, and humidity changed in a way that "
                "violates physical coupling - cannot be a real atmospheric event."
            ),
        }

    # Rule 3: If the anomaly is a power failure -> definitely fault
    if anomaly_class == "Power Failure":
        return {
            "genuine_weather_event": False,
            "weather_verdict_reason": (
                "All parameters collapsed to zero simultaneously. "
                "No atmospheric state produces this - sensor/power failure."
            ),
        }
        # Rule 3.5: Total collapse -> definitely fault
    if mv_verdict == "total_collapse":
        return {
            "genuine_weather_event": False,
            "weather_verdict_reason": (
                "All parameters collapsed to zero simultaneously. "
                "This is a total sensor/power failure, not a weather event."
            ),
        }


    # Rule 4: If physics coupling is implausible -> likely fault
    if mv_verdict == "physically_implausible":
        return {
            "genuine_weather_event": False,
            "weather_verdict_reason": (
                "Temperature change is not coupled with humidity change - "
                "inconsistent with a physical weather event."
            ),
        }

    # Rule 5: If anomaly type is a spike or drop with no spatial support -> fault
    if anomaly_class in ("Temperature Spike", "Temperature Drop", "Frozen Sensor"):
        return {
            "genuine_weather_event": False,
            "weather_verdict_reason": (
                f"{anomaly_class} signature with no regional corroboration - "
                "consistent with sensor fault."
            ),
        }

    # Default: cannot determine
    return {
        "genuine_weather_event": False,
        "weather_verdict_reason": (
            "Anomaly detected without positive weather-event signature. "
            "Flagged as likely sensor fault."
        ),
    }


def _compute_defensibility(row, evidence: dict, multivariate: dict, weather_verdict: dict) -> dict:
    """
    A defensibility block that explicitly states:
      - What evidence supports the conclusion
      - What evidence is missing or weak
      - Known limitations
      - Recommended operator action
      - Meaning of the confidence score

    This block answers the "what if ground conditions differ?" question
    before it is asked.
    """
    # Evidence for the fault hypothesis
    evidence_for = []
    breakdown = evidence.get("evidence_breakdown", {})
    for source, d in breakdown.items():
        if d.get("fired"):
            evidence_for.append(source)

    # Evidence against (counter-evidence)
    evidence_against = []
    if bool(int(row.get("spatial_common_event_flag", 0) or 0)):
        evidence_against.append("regional_change_detected")

    # Known limitations
    limitations = [
        "Assumes physical coupling rules apply - extreme localized events "
        "could produce similar signatures."
    ]
    if multivariate.get("verdict") == "insufficient_data":
        limitations.append("Multivariate deltas unavailable for this reading.")
    if weather_verdict.get("genuine_weather_event"):
        limitations.append("Classified as possible regional weather event.")

    return {
        "evidence_for_fault": evidence_for,
        "evidence_against_fault": evidence_against,
        "known_limitations": limitations,
        "operator_action": "Review recommended. Original reading preserved.",
        "confidence_meaning": "Evidence strength, not probability of failure.",
    }
    # Determine expected direction of humidity change
    expected_rh_direction = "up" if d_t < 0 else "down"
    observed_rh_direction = "up" if d_h > 0 else ("down" if d_h < 0 else "flat")

    # Tolerance: if humidity moves less than ~20% of what's expected,
    # the coupling is considered weak.
    coupling_ok = (
        (expected_rh_direction == "up" and d_h > 0.5) or
        (expected_rh_direction == "down" and d_h < -0.5)
    )

    if coupling_ok:
        return {
            "verdict": "physically_plausible",
            "reason": (
                f"Temperature moved {d_t:+.1f}°C with humidity {d_h:+.1f}% "
                f"(expected {expected_rh_direction}). Coupling consistent with "
                "physical atmospheric behavior."
            ),
            "details": details,
        }

    return {
        "verdict": "physically_implausible",
        "reason": (
            f"Temperature moved {d_t:+.1f}°C while humidity changed only "
            f"{d_h:+.1f}% (expected {expected_rh_direction}). "
            "This violates physical coupling — stronger evidence of sensor fault."
        ),
        "details": details,
    }
# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def build_backend_output(
    scored_df: pd.DataFrame,
    health_df: pd.DataFrame,
    meta_df: pd.DataFrame = None,
    obs_df: pd.DataFrame = None,
) -> list:
    """
    Build a clean list of alert dicts from scored + health DataFrames.

    Parameters
    ----------
    scored_df : pd.DataFrame
        Output of explain_dataframe(score_anomalies(classify_anomalies(...)))
        Must contain the columns listed in REQUIRED_COLUMNS.
    health_df : pd.DataFrame
        Output of calculate_sensor_health(scored_df).
        Must contain: station_id, maintenance_status, maintenance_recommendation.

    Returns
    -------
    list of dict
        One dict per anomaly row, ready for JSON serialization.
    """    # Fallback if caller didn't provide metadata / observations.
    if meta_df is None:
        meta_df = pd.read_csv("data/station_metadata.csv")
    if obs_df is None:
        obs_df = pd.read_csv("data/test_injected_aws.csv")
        obs_df["timestamp"] = pd.to_datetime(obs_df["timestamp"])

  
    # Validate required columns.
    
    missing = [c for c in REQUIRED_COLUMNS if c not in scored_df.columns]
    if missing:
        raise ValueError(
            f"scored_df is missing required columns: {missing}. "
            f"Available: {list(scored_df.columns)}"
        )

    if "station_id" not in health_df.columns:
        raise ValueError(
            "health_df must contain 'station_id'. "
            f"Available: {list(health_df.columns)}"
        )

    # Build a per-station lookup of health info.
    health_lookup = {}
    for _, h in health_df.iterrows():
        sid = h["station_id"]
        health_lookup[sid] = {
            "sensor_health": HEALTH_MAP.get(
                str(h.get("maintenance_status", "")).strip(),
                "unknown",
            ),
            "maintenance_recommendation": str(
                h.get("maintenance_recommendation", "")
            ).strip(),
        }

    # Emit one alert per anomaly row.
    alerts = []
    for _, row in scored_df.iterrows():
        if not _row_is_anomaly(row):
            continue

        sid = str(row["station_id"])
        health_info = health_lookup.get(
            sid,
            {"sensor_health": "unknown", "maintenance_recommendation": ""},
        )

        # Compute self-healing corrected values using neighbours.
        corrected = _compute_corrected_values(row, meta_df, obs_df)
        corrected = _compute_corrected_values(row, meta_df, obs_df)

        priority = _compute_priority(
            severity=row.get("severity", ""),
            confidence=row.get("anomaly_confidence"),
            spatial_isolated=bool(int(row.get("spatial_isolated_flag", 0) or 0)),
        )

        evidence = _compute_evidence_breakdown(row)
        counter_reasoning = _compute_counter_reasoning(row)
        trust_score = _compute_trust_score(row, evidence["evidence_breakdown"])
        event_class = _compute_event_class(row)
        physical_reasoning = _compute_physical_reasoning(row)
        multivariate = _compute_multivariate_analysis(row)
        weather_verdict = _compute_genuine_weather_verdict(row, multivariate)
        defensibility = _compute_defensibility(row, evidence, multivariate, weather_verdict)

        alert = {
            "station_id": sid,
            "timestamp": str(row["timestamp"]),
            "temperature": _safe_float(row.get("temperature")),
            "pressure": _safe_float(row.get("pressure")),
            "humidity": _safe_float(row.get("humidity")),
            "status": "anomaly",
            "anomaly_type": str(row.get("anomaly_class", "Unknown")),
            "confidence": _safe_int(row.get("anomaly_confidence")),
            "severity": str(row.get("severity", "Unknown")),
            "reasons": _build_reasons(row),
            "sensor_health": health_info["sensor_health"],
            "maintenance_recommendation": health_info["maintenance_recommendation"],
                       "priority": priority,
            "evidence_breakdown": evidence["evidence_breakdown"],
            "decision_basis": evidence["decision_basis"],
            "counter_evidence": evidence["counter_evidence"],
            "counter_reasoning": counter_reasoning,
            "trust_score": trust_score,
            "event_class": event_class,
            "physical_reasoning": physical_reasoning,
            "multivariate_analysis": multivariate,
            "genuine_weather_event": weather_verdict["genuine_weather_event"],
            "weather_verdict_reason": weather_verdict["weather_verdict_reason"],
            "defensibility": defensibility,
            "corrected_temperature": corrected["corrected_temperature"],
            "corrected_pressure": corrected["corrected_pressure"],
            "corrected_humidity": corrected["corrected_humidity"],
            "correction_confidence": corrected["correction_confidence"],
            "correction_basis": corrected["correction_basis"],
        }
        alerts.append(alert)
    return alerts


def save_alerts(alerts: list, path: str = OUTPUT_FILE) -> str:
    """Write alerts list to JSON. Returns the path written."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, default=str)
    return path


# ----------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import contextlib
    import io

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)

    from feature_engineering import build_features
    from qc_rules import apply_qc_rules
    from spatial_analysis import apply_spatial_analysis
    from temporal_detector import apply_temporal_detector
    from anomaly_classifier import classify_anomalies
    from scoring import score_anomalies
    from explainer import explain_dataframe
    from sensor_health import calculate_sensor_health

    print("=" * 60)
    print("SkyGuard AI — Backend Output Demo")
    print("=" * 60)

    # 1. Load test data.
    obs = pd.read_csv("data/test_injected_aws.csv")
    obs["timestamp"] = pd.to_datetime(obs["timestamp"])

    # 2. Features + QC.
    feats = build_features(obs)
    qc = apply_qc_rules(feats)
    qc_cols = ["station_id", "timestamp"] + [
        c for c in qc.columns if c.startswith("qc_")
    ]
    qc = qc[qc_cols].copy()
    

    # 3. Spatial.
    metadata = pd.read_csv("data/station_metadata.csv")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spatial = apply_spatial_analysis(obs, metadata)
    spatial_cols = ["station_id", "timestamp"] + [
        c for c in spatial.columns if c.startswith("spatial_")
    ]
    spatial = spatial[spatial_cols].copy()

    # 4. Temporal.
    temporal = apply_temporal_detector(obs)
    temp_cols = ["station_id", "timestamp"] + [
        c for c in temporal.columns if c.startswith("temporal_")
    ]
    temporal = temporal[temp_cols].copy()

    # 5. Isolation Forest predictions.
    if_df = pd.read_csv("data/isolation_forest_predictions.csv")
    if_df["timestamp"] = pd.to_datetime(if_df["timestamp"])
    if_keep = ["station_id", "timestamp", "predicted_anomaly", "anomaly_score"]
    if_df = if_df[[c for c in if_keep if c in if_df.columns]].copy()

    # 6. Merge all evidence (drop duplicate ground-truth cols from IF file).
    # 6. Merge all evidence (drop duplicate ground-truth cols from IF file).
    joined = obs.merge(if_df, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(qc, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(spatial, on=["station_id", "timestamp"], how="left")
    joined = joined.merge(temporal, on=["station_id", "timestamp"], how="left")

    # Merge delta columns for physical reasoning.
    delta_cols = ["station_id", "timestamp", "d_temperature", "d_pressure", "d_humidity"]
    delta_cols = [c for c in delta_cols if c in feats.columns]
    joined = joined.merge(feats[delta_cols], on=["station_id", "timestamp"], how="left")

    # 7. Classify + score.
    classified = classify_anomalies(joined)
    scored = score_anomalies(classified)

    # Run the fusion layer to get fused_any_flag.
    from evidence_fusion import fuse_evidence
    fused = fuse_evidence(scored)
    # Save the fused predictions to a CSV so the evaluator can read them.
    import os
    os.makedirs("data", exist_ok=True)
    fused_out_cols = [
        "timestamp", "station_id", "temperature", "pressure", "humidity",
        "is_anomaly", "anomaly_type", "injected_parameter",
        "predicted_anomaly", "anomaly_score",
        "fused_score", "fused_label", "fused_any_flag",
        "fused_evidence_count", "fused_counter_evidence",
        "anomaly_class", "anomaly_confidence", "severity",
    ]
    present = [c for c in fused_out_cols if c in fused.columns]
    fused[present].to_csv("data/fused_predictions.csv", index=False)
    print(f"[save] Fused predictions saved to data/fused_predictions.csv ({len(fused)} rows)")

    explained = explain_dataframe(fused)
    health = calculate_sensor_health(explained)

    # 9. Build backend output.
    alerts = build_backend_output(explained, health, meta_df=metadata, obs_df=obs)

    # 10. Save + print.
    path = save_alerts(alerts)
    print(f"\nTotal anomalies: {len(alerts)}")
    print(f"Saved to: {path}\n")
    print("First 5 alerts (pretty-printed):\n")
    for a in alerts[:5]:
        print(json.dumps(a, indent=2, default=str))
        print("-" * 60)