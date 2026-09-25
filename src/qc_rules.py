"""
src/qc_rules.py
SkyGuard AI - STEP 14: Rule-Based QC Engine.

Hybrid detector design:
    - Statistical anomaly detection (Isolation Forest baseline, later an
      autoencoder) provides sensitivity to subtle / unknown fault patterns.
    - Rule-based quality control (this file) provides EXPLAINABLE,
      physics-informed sanity checks that catch obvious garbage, frozen
      sensors, isolated single-variable jumps, and communication gaps.

The QC flags produced here are intended to be FUSED later with the ML
predictions in a separate future step. This file does NOT implement
fusion, does NOT train any model, and does NOT build a dashboard.

Design principles:
  1. Every rule emits a human-readable reason string.
  2. Thresholds are configurable via QCConfig. They are OPERATIONAL
     HEURISTICS, NOT WMO or any other formal standards.
  3. Rules run PER STATION (no cross-station logic) so they scale to
     large networks and can run at the edge.
  4. Deterministic and O(n) per station.
  5. Each rule emits a boolean flag column + reason string. The engine
     also emits aggregate columns: qc_any_flag, qc_flag_count, qc_reasons.

Uses only pandas and numpy. No sklearn, no ML.
"""

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Configuration (dataclass)
# ----------------------------------------------------------------------
@dataclass
class QCConfig:
    """
    Configuration for the QC rules engine.

    Every threshold here is an OPERATIONAL HEURISTIC. None of these
    values are WMO or any other formal standard. They are sensible
    defaults for a prototype; every field is configurable so the system
    can be adapted per network, climate regime, or sensor model without
    editing code.

    Rule 4(b) uses TWO conditions that must BOTH be met for a row to be
    flagged as an isolated single-variable shift:
      (1) ABSOLUTE FLOOR: |d_x| > INTERNAL_*_FLOOR. This is a MINIMUM
          PHYSICAL CHANGE below which we never flag, no matter what the
          rolling std says. It prevents the rule from firing on natural
          micro-variability (e.g. humidity noise).
      (2) STATISTICAL TEST: |d_x| > INTERNAL_K * rolling_std(d_x). This
          is a test relative to the variable's own recent variability.
          It prevents the rule from firing on changes that are large in
          absolute terms but normal for the current regime.
    BOTH conditions must be met. The OTHER two variables must be BELOW
    their respective FLOORS (in absolute terms, not k*sigma) for the
    row to count as an "isolated" shift.
    """

    # ---- Rule 1: Range / limit check ----
    TEMP_MIN: float = -60.0          # deg C, operational sanity lower bound
    TEMP_MAX: float = 60.0          # deg C, operational sanity upper bound
    PRES_MIN: float | None = 800.0  # hPa, wide envelope; None to skip
    PRES_MAX: float | None = 1100.0 # hPa, wide envelope; None to skip

    # ---- Rule 2: Temporal consistency ----
    TEMPORAL_WINDOW: int = 96       # rolling window (samples); ~24h at 15-min
    TEMPORAL_K: float = 5.0         # flag |d_x| > k * rolling_std(d_x)

    # ---- Rule 3: Persistence / frozen-value ----
    PERSISTENCE_N: int = 8          # min consecutive identical samples to flag
    PERSISTENCE_MODE: str = "exact"  # "exact" or "resolution_aware"
    PERSISTENCE_TOL: float = 0.0    # only used in "resolution_aware" mode;
                                     # must be > 0 if mode == "resolution_aware"

    # ---- Rule 4: Internal consistency (T/P/H) ----
    # Rule 4(a) - dew-point physical impossibility.
    DEWPOINT_TOL: float = 0.5       # Td may exceed T by this much before flag
    MAGNUS_B: float = 17.62         # Magnus formula constant
    MAGNUS_C: float = 243.12        # Magnus formula constant

    # Rule 4(b) - statistically principled isolated-shift check.
    INTERNAL_WINDOW: int = 96       # rolling window (samples); ~24h at 15-min
    INTERNAL_K: float = 5.0         # flag |d_x| > k * rolling_std(d_x)
    # Absolute floors: never flag below these, regardless of sigma.
    INTERNAL_TEMP_CHANGE_FLOOR: float = 3.0       # deg C
    INTERNAL_PRESSURE_CHANGE_FLOOR: float = 0.5   # hPa
    INTERNAL_HUMIDITY_CHANGE_FLOOR: float = 10.0  # %

    # DEPRECATED (kept for backward compatibility only).
    # The old names suggested "any change above this is suspicious", which
    # is exactly the mistake being fixed: the rule fired whenever a
    # variable moved faster than an arbitrary constant, not when a true
    # isolated sensor-level shift occurred. Use the _FLOOR fields above as
    # the actual absolute thresholds; these old fields are no longer read
    # by Rule 4(b) and are retained only so older config files / pickles
    # do not break.
    INTERNAL_TEMP_CHANGE: float = 5.0       # DEPRECATED, use _TEMP_CHANGE_FLOOR
    INTERNAL_PRESSURE_CHANGE: float = 1.0   # DEPRECATED, use _PRESSURE_CHANGE_FLOOR
    INTERNAL_HUMIDITY_CHANGE: float = 5.0   # DEPRECATED, use _HUMIDITY_CHANGE_FLOOR

    # ---- Rule 5: Gap detection ----
    GAP_MULTIPLIER: float = 2.0     # gap > multiplier * median cadence


# Required input columns (output of src/feature_engineering.build_features).
REQUIRED_COLUMNS = [
    "station_id", "timestamp",
    "temperature", "pressure", "humidity",
    "d_temperature", "d_pressure", "d_humidity",
]

# Five rule flag columns + five reason columns.
FLAG_COLUMNS = [
    "qc_range_flag",
    "qc_temporal_flag",
    "qc_persistence_flag",
    "qc_internal_flag",
    "qc_gap_flag",
]
REASON_COLUMNS = [
    "qc_range_reason",
    "qc_temporal_reason",
    "qc_persistence_reason",
    "qc_internal_reason",
    "qc_gap_reason",
]


# ----------------------------------------------------------------------
# Rule 1: Range / limit check (per row)
# ----------------------------------------------------------------------
def _rule_range(group: pd.DataFrame, config: QCConfig):
    """
    Rule 1 - Range / limit check.

    Fires when temperature, humidity, or pressure falls outside its
    configured operational envelope. Humidity uses the physical
    [0, 100] bound; the others use the configurable QCConfig fields.
    Pressure check is skipped entirely if PRES_MIN or PRES_MAX is None.
    """
    n = len(group)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    # Vectorized range violations (NaN comparisons return False, which
    # is the desired behavior - we do not flag NaN values here).
    t_out = ((group["temperature"] < config.TEMP_MIN)
             | (group["temperature"] > config.TEMP_MAX)).to_numpy()
    h_out = ((group["humidity"] < 0)
             | (group["humidity"] > 100)).to_numpy()
    if config.PRES_MIN is not None and config.PRES_MAX is not None:
        p_out = ((group["pressure"] < config.PRES_MIN)
                 | (group["pressure"] > config.PRES_MAX)).to_numpy()
    else:
        p_out = np.zeros(n, dtype=bool)

    for i in range(n):
        parts = []
        if t_out[i]:
            parts.append(
                f"temperature out of range [{config.TEMP_MIN},{config.TEMP_MAX}]"
            )
        if h_out[i]:
            parts.append("humidity out of [0,100]")
        if p_out[i]:
            parts.append(
                f"pressure out of range [{config.PRES_MIN},{config.PRES_MAX}]"
            )
        if parts:
            flags[i] = 1
            reasons[i] = "; ".join(parts)
    return flags, reasons


# ----------------------------------------------------------------------
# Rule 2: Temporal consistency (per row, needs valid d_*)
# ----------------------------------------------------------------------
def _rule_temporal(group: pd.DataFrame, config: QCConfig):
    """
    Rule 2 - Temporal consistency check.

    For each of {d_temperature, d_pressure, d_humidity}:
        flag if |d_x| > k * rolling_std_of_d_x
    Rolling std is computed PER STATION with window=TEMPORAL_WINDOW
    (default 96 samples, ~24h at 15-min cadence).

    Rows with NaN d_x (the first row per station) are NOT flagged -
    qc_temporal_flag stays 0 and the reason does not fire. Rows where
    rolling_std is 0 or NaN (e.g. at start of series) are also skipped
    per spec.
    """
    n = len(group)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    for var, dvar in [("temperature", "d_temperature"),
                      ("pressure",    "d_pressure"),
                      ("humidity",    "d_humidity")]:
        dx = group[dvar]
        # Rolling std per station. Default min_periods=window, so the
        # first (window-1) rows of each station have NaN std and are
        # skipped automatically.
        rolling_std = dx.rolling(window=config.TEMPORAL_WINDOW).std()
        threshold = config.TEMPORAL_K * rolling_std

        # Skip rows where d_x is NaN, rolling_std is NaN, or rolling_std is 0.
        valid = dx.notna() & rolling_std.notna() & (rolling_std > 0)
        flagged = valid & (dx.abs() > threshold)
        for i in np.where(flagged.to_numpy())[0]:
            reason = (f"large change in {var} "
                      f"(d={dx.iloc[i]:.3f}, "
                      f"k*sigma={threshold.iloc[i]:.3f})")
            if flags[i] == 1:
                reasons[i] = reasons[i] + "; " + reason
            else:
                flags[i] = 1
                reasons[i] = reason
    return flags, reasons


# ----------------------------------------------------------------------
# Rule 3: Persistence / frozen-value check (per row)
# ----------------------------------------------------------------------
def _rule_persistence(group: pd.DataFrame, config: QCConfig):
    """
    Rule 3 - Persistence / frozen-value check.

    For each of {temperature, pressure, humidity}: flag if the value
    has been equal for at least PERSISTENCE_N consecutive samples.

    Equality mode is configurable:
      - "exact"             : bit-for-bit equality (default)
      - "resolution_aware"  : |diff| < PERSISTENCE_TOL (tol must be > 0)

    Runs of length 2 or 3 are NOT flagged (PERSISTENCE_N default 8).
    """
    n = len(group)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    for var in ["temperature", "pressure", "humidity"]:
        values = group[var]

        if config.PERSISTENCE_MODE == "exact":
            same = (values == values.shift()).fillna(False)
        elif config.PERSISTENCE_MODE == "resolution_aware":
            if config.PERSISTENCE_TOL <= 0:
                raise ValueError(
                    "PERSISTENCE_TOL must be > 0 in 'resolution_aware' mode."
                )
            same = (values.diff().abs() < config.PERSISTENCE_TOL).fillna(False)
        else:
            raise ValueError(
                f"Unknown PERSISTENCE_MODE: {config.PERSISTENCE_MODE!r}. "
                "Use 'exact' or 'resolution_aware'."
            )

        # Run length ending at each position (1-indexed).
        # A new run starts wherever `same` is False (value differs from prev).
        # groupby on the resulting run_id and cumcount gives the rank within
        # each run; +1 makes it 1-indexed. O(n) per variable per station.
        run_id = (~same).cumsum()
        run_length = values.groupby(run_id).cumcount() + 1

        flagged = (run_length >= config.PERSISTENCE_N).to_numpy()
        for i in np.where(flagged)[0]:
            reason = (f"{var} frozen for "
                      f"{int(run_length.iloc[i])} consecutive samples")
            if flags[i] == 1:
                reasons[i] = reasons[i] + "; " + reason
            else:
                flags[i] = 1
                reasons[i] = reason
    return flags, reasons


# ----------------------------------------------------------------------
# Rule 4: Internal consistency (T/P/H) - SUPPORTING EVIDENCE only
# ----------------------------------------------------------------------
def _rule_internal(group: pd.DataFrame, config: QCConfig):
    """
    Rule 4 - Internal consistency (T/P/H).

    This rule provides SUPPORTING EVIDENCE only. It must NEVER be
    treated as proof of sensor failure on its own.

    Two independent sub-checks:

    (a) Dew-point physical consistency (Magnus formula):
          gamma = ln(RH/100) + (b*T)/(c+T)
          Td    = (c*gamma)/(b-gamma)
        Flag when Td > T + DEWPOINT_TOL. Dew point cannot exceed air
        temperature - this is a physical impossibility, not an
        assumed correlation.

    (b) Isolated single-variable-shift check (statistically principled):
        For each variable d_x, compute rolling_std(d_x) per station with
        window=INTERNAL_WINDOW. A row is flagged as an "isolated X shift"
        when BOTH:
          (1) |d_x| > INTERNAL_*_FLOOR  (absolute floor: minimum physical
              change below which we never flag, regardless of sigma)
          (2) |d_x| > INTERNAL_K * rolling_std(d_x)  (statistical test
              relative to the variable's own recent variability)
        AND rolling_std is not NaN and > 0, AND the OTHER two d_* are
        BELOW their respective floors (absolute, not k*sigma). The
        "other two stable" condition uses absolute floors because we care
        that they didn't move appreciably in absolute terms, not relative
        to their own history.
    """
    n = len(group)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    T = group["temperature"].to_numpy(dtype=float)
    P = group["pressure"].to_numpy(dtype=float)
    H = group["humidity"].to_numpy(dtype=float)
    dT = group["d_temperature"].to_numpy(dtype=float)
    dP = group["d_pressure"].to_numpy(dtype=float)
    dH = group["d_humidity"].to_numpy(dtype=float)

    # ---- (a) Dew-point physical impossibility ----
    b = config.MAGNUS_B
    c = config.MAGNUS_C
    with np.errstate(all="ignore"):
        gamma = np.log(H / 100.0) + (b * T) / (c + T)
        Td = (c * gamma) / (b - gamma)
    valid_tph = (~np.isnan(T)) & (~np.isnan(P)) & (~np.isnan(H)) & (H > 0)
    dewpoint_violation = valid_tph & (~np.isnan(Td)) & (Td > T + config.DEWPOINT_TOL)
    for i in np.where(dewpoint_violation)[0]:
        reason = (f"dew point ({Td[i]:.2f}) > "
                  f"temperature ({T[i]:.2f})")
        if flags[i] == 1:
            reasons[i] = reasons[i] + "; " + reason
        else:
            flags[i] = 1
            reasons[i] = reason

    # ---- (b) Isolated single-variable shift (statistically principled) ----
    # For each variable d_x, compute rolling_std(d_x) per station (group is
    # already per-station) with window=INTERNAL_WINDOW. A row is flagged as
    # an "isolated X shift" when BOTH:
    #   (1) |d_x| > INTERNAL_*_FLOOR  (absolute floor)
    #   (2) |d_x| > INTERNAL_K * rolling_std(d_x)  (statistical test)
    # AND rolling_std is not NaN and > 0, AND the OTHER two d_* are BELOW
    # their respective floors (absolute, not k*sigma).
    #
    # The "other two stable" condition uses ABSOLUTE floors because we only
    # care that they didn't move appreciably in absolute terms - not that
    # they didn't move relative to their own history.
    all_d_valid = (~np.isnan(dT)) & (~np.isnan(dP)) & (~np.isnan(dH))

    # Rolling std per variable (per station, since group is per station).
    rsT = pd.Series(dT).rolling(window=config.INTERNAL_WINDOW).std().to_numpy()
    rsP = pd.Series(dP).rolling(window=config.INTERNAL_WINDOW).std().to_numpy()
    rsH = pd.Series(dH).rolling(window=config.INTERNAL_WINDOW).std().to_numpy()
    kT = config.INTERNAL_K * rsT  # numpy array
    kP = config.INTERNAL_K * rsP
    kH = config.INTERNAL_K * rsH

    # shift_x = absolute floor AND statistical test AND valid rolling std.
    shift_T = (np.abs(dT) > config.INTERNAL_TEMP_CHANGE_FLOOR) & \
              (np.abs(dT) > kT) & \
              (~np.isnan(rsT)) & (rsT > 0)
    shift_P = (np.abs(dP) > config.INTERNAL_PRESSURE_CHANGE_FLOOR) & \
              (np.abs(dP) > kP) & \
              (~np.isnan(rsP)) & (rsP > 0)
    shift_H = (np.abs(dH) > config.INTERNAL_HUMIDITY_CHANGE_FLOOR) & \
              (np.abs(dH) > kH) & \
              (~np.isnan(rsH)) & (rsH > 0)

    # Isolated X shift: shift_X AND other two below their floors.
    # (Mutually exclusive by construction - if e.g. dT exceeds TEMP_FLOOR
    #  then the "other two stable" condition for an isolated T shift
    #  requires dP < PRESSURE_FLOOR, which contradicts shift_P's requirement
    #  that dP > PRESSURE_FLOOR.)
    t_shifted = all_d_valid & shift_T & \
                (np.abs(dP) < config.INTERNAL_PRESSURE_CHANGE_FLOOR) & \
                (np.abs(dH) < config.INTERNAL_HUMIDITY_CHANGE_FLOOR)
    p_shifted = all_d_valid & shift_P & \
                (np.abs(dT) < config.INTERNAL_TEMP_CHANGE_FLOOR) & \
                (np.abs(dH) < config.INTERNAL_HUMIDITY_CHANGE_FLOOR)
    h_shifted = all_d_valid & shift_H & \
                (np.abs(dT) < config.INTERNAL_TEMP_CHANGE_FLOOR) & \
                (np.abs(dP) < config.INTERNAL_PRESSURE_CHANGE_FLOOR)

    for i in np.where(t_shifted)[0]:
        reason = (f"isolated temperature shift "
                  f"(dT={dT[i]:.2f}, k*sigma={kT[i]:.2f}, "
                  f"while dP={dP[i]:.2f}, dRH={dH[i]:.2f})")
        if flags[i] == 1:
            reasons[i] = reasons[i] + "; " + reason
        else:
            flags[i] = 1
            reasons[i] = reason
    for i in np.where(p_shifted)[0]:
        reason = (f"isolated pressure shift "
                  f"(dP={dP[i]:.2f}, k*sigma={kP[i]:.2f}, "
                  f"while dT={dT[i]:.2f}, dRH={dH[i]:.2f})")
        if flags[i] == 1:
            reasons[i] = reasons[i] + "; " + reason
        else:
            flags[i] = 1
            reasons[i] = reason
    for i in np.where(h_shifted)[0]:
        reason = (f"isolated humidity shift "
                  f"(dRH={dH[i]:.2f}, k*sigma={kH[i]:.2f}, "
                  f"while dT={dT[i]:.2f}, dP={dP[i]:.2f})")
        if flags[i] == 1:
            reasons[i] = reasons[i] + "; " + reason
        else:
            flags[i] = 1
            reasons[i] = reason
    return flags, reasons


# ----------------------------------------------------------------------
# Rule 5: Missing observation / communication-gap (per timeline)
# ----------------------------------------------------------------------
def _rule_gap(group: pd.DataFrame, config: QCConfig):
    """
    Rule 5 - Missing observation / communication-gap check.

    Operates on the TIMELINE per station, not on individual rows.

    Infers the expected cadence (median time delta per station) and
    flags rows that IMMEDIATELY PRECEDE a gap larger than
    GAP_MULTIPLIER * expected cadence. A missing row cannot be flagged
    directly, so we annotate its predecessor.

    Leading gaps (gaps before the first observation) are intentionally
    NOT detected: with no predecessor observation there is no reference
    point from which to establish the gap.
    """
    n = len(group)
    flags = np.zeros(n, dtype=int)
    reasons = [""] * n

    if n < 2:
        return flags, reasons

    # Group is already sorted by timestamp (caller ensures this).
    timestamps = pd.to_datetime(group["timestamp"].to_numpy())
    # deltas[i] (for i in 1..n-1) is the gap between timestamps[i-1] and
    # timestamps[i].
    deltas = pd.Series(timestamps).diff().iloc[1:]  # length n-1
    if deltas.empty:
        return flags, reasons

    expected = deltas.median()
    if pd.isna(expected) or expected == pd.Timedelta(0):
        return flags, reasons  # cannot establish cadence

    threshold = config.GAP_MULTIPLIER * expected

    # deltas.index is 1..n-1 (positional index within the group).
    # For each gap at position i, the row immediately preceding the gap
    # is at position i-1. We annotate that row.
    for pos in deltas.index:
        delta = deltas[pos]
        if pd.isna(delta) or delta <= threshold:
            continue
        n_samples_gap = int(round(delta / expected))
        n_minutes_gap = int(delta.total_seconds() / 60.0)
        reason = (f"gap of {n_samples_gap} samples "
                  f"({n_minutes_gap} minutes) after this row")
        flags[pos - 1] = 1
        reasons[pos - 1] = reason
    return flags, reasons


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def apply_qc_rules(df: pd.DataFrame,
                   config: QCConfig | None = None) -> pd.DataFrame:
    """
    Apply all five QC rules per station and return the enriched DataFrame.

    The input DataFrame must be the output of
    src.feature_engineering.build_features() (i.e. it must contain at
    least station_id, timestamp, temperature, pressure, humidity,
    d_temperature, d_pressure, d_humidity).

    Adds these columns (does NOT drop or rename existing columns):
      - qc_range_flag, qc_range_reason
      - qc_temporal_flag, qc_temporal_reason
      - qc_persistence_flag, qc_persistence_reason
      - qc_internal_flag, qc_internal_reason
      - qc_gap_flag, qc_gap_reason
      - qc_any_flag       (0/1)  - any of the five flags is 1
      - qc_flag_count     (int)  - sum of the five flags
      - qc_reasons        (str)  - " | " joined non-empty reasons

    Returns a copy of the input; the input is NOT mutated in place.
    """
    if config is None:
        config = QCConfig()

    # Validate required columns.
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Required: {REQUIRED_COLUMNS}."
        )

    # Work on a copy; do NOT mutate input.
    out = df.copy().reset_index(drop=True)

    # Initialize output columns.
    for c in FLAG_COLUMNS:
        out[c] = 0
    for c in REASON_COLUMNS:
        out[c] = ""

    # Dispatch each rule per station.
    rule_specs = [
        (_rule_range,       "qc_range_flag",       "qc_range_reason"),
        (_rule_temporal,    "qc_temporal_flag",    "qc_temporal_reason"),
        (_rule_persistence, "qc_persistence_flag", "qc_persistence_reason"),
        (_rule_internal,    "qc_internal_flag",     "qc_internal_reason"),
        (_rule_gap,         "qc_gap_flag",          "qc_gap_reason"),
    ]

    for _station_id, group in out.groupby("station_id"):
        # Sort by timestamp to ensure chronological order for rules
        # that depend on time (Rule 2, 3, 5).
        group = group.sort_values("timestamp")
        # Indices into `out` (preserved by sort_values).
        idx = group.index.to_numpy()

        for rule_fn, flag_col, reason_col in rule_specs:
            flags, reasons = rule_fn(group, config)
            out.loc[idx, flag_col] = flags
            out.loc[idx, reason_col] = np.asarray(reasons, dtype=object)

    # Aggregate columns.
    flag_matrix = out[FLAG_COLUMNS].to_numpy()
    out["qc_any_flag"] = (flag_matrix.sum(axis=1) > 0).astype(int)
    out["qc_flag_count"] = flag_matrix.sum(axis=1).astype(int)

    # qc_reasons: " | " joined non-empty reason strings.
    reason_matrix = out[REASON_COLUMNS].to_numpy().tolist()
    out["qc_reasons"] = [" | ".join([r for r in row if r]) for row in reason_matrix]

    return out


# ----------------------------------------------------------------------
# Demo (does NOT save any file; does NOT build a dashboard; does NOT
# mutate any CSV).
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Sibling import shim so feature_engineering.py is importable whether
    # this file is run as `python src/qc_rules.py` or `python -m src.qc_rules`.
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from feature_engineering import build_features  # noqa: E402

    print("=" * 70)
    print("SkyGuard AI - STEP 14: Rule-Based QC Engine (demo)")
    print("=" * 70)

    for label, path in [("NORMAL  ", "data/normal_aws_data.csv"),
                        ("INJECTED", "data/test_injected_aws.csv")]:
        print(f"\n--- {label} ({path}) ---")
        df = pd.read_csv(path)
        feats = build_features(df)
        result = apply_qc_rules(feats)

        print(f"Total rows: {len(result)}")
        for rule_name, flag_col in [
            ("Rule 1 - Range",         "qc_range_flag"),
            ("Rule 2 - Temporal",      "qc_temporal_flag"),
            ("Rule 3 - Persistence",   "qc_persistence_flag"),
            ("Rule 4 - Internal",      "qc_internal_flag"),
            ("Rule 5 - Gap",           "qc_gap_flag"),
        ]:
            n_flagged = int(result[flag_col].sum())
            pct = 100.0 * n_flagged / max(len(result), 1)
            print(f"  {rule_name:<22s}: {n_flagged:>6} rows flagged "
                  f"({pct:>6.2f}%)")

        # Rule 4 breakdown by sub-check / shifted variable, so we can see
        # whether the new statistically-principled logic still has a
        # humidity bias. Rows may appear in multiple sub-checks if both
        # 4(a) and 4(b) fire on the same row; isolated X shifts are
        # mutually exclusive with each other by construction.
        rule4_mask = result["qc_internal_flag"] == 1
        rule4_reasons = result.loc[rule4_mask, "qc_internal_reason"]
        n_dew = int(rule4_reasons.str.contains("dew point", regex=False).sum())
        n_t_shift = int(rule4_reasons.str.contains(
            "isolated temperature shift", regex=False).sum())
        n_p_shift = int(rule4_reasons.str.contains(
            "isolated pressure shift", regex=False).sum())
        n_h_shift = int(rule4_reasons.str.contains(
            "isolated humidity shift", regex=False).sum())
        print("\n  Rule 4 breakdown (rows may appear in multiple sub-checks):")
        print(f"    dew point violation            : {n_dew}")
        print(f"    isolated temperature shift     : {n_t_shift}")
        print(f"    isolated pressure shift        : {n_p_shift}")
        print(f"    isolated humidity shift        : {n_h_shift}")

        # Top 5 rows by qc_flag_count, with qc_reasons.
        top5 = result.nlargest(5, "qc_flag_count")[
            ["timestamp", "station_id", "qc_flag_count", "qc_reasons"]
        ]
        print("\n  Top 5 rows by qc_flag_count:")
        # Indent each line of the table for readability.
        for line in top5.to_string(index=False).splitlines():
            print("    " + line)