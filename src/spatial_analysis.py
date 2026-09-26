"""
src/spatial_analysis.py
SkyGuard AI - STEP 15: Spatial Consistency Analysis.

Spatial analysis adds a FOURTH independent line of evidence to the
hybrid SkyGuard AI detector:
    - Isolation Forest baseline (per-station, no spatial context)
    - Rule-based QC engine (per-station, physics-informed)
    - Spatial consistency (this file, cross-station context)

The central question: does a station's reading agree with its
geographical neighbours at the same time?

A single station reporting 52 deg C while neighbours report 30-32 deg C
is strong evidence of an isolated sensor fault.
A single station reporting 36 deg C while neighbours report 35-37 deg C
is weak evidence of a fault - possibly a genuine local weather event.

Spatial evidence is SUPPORTING EVIDENCE ONLY. It must NEVER be presented
as proof of a fault on its own. Its primary role is to SUPPRESS false
alarms on genuine weather events that other detectors flag, and to
STRENGTHEN the case against isolated station deviations.

Uses only pandas and numpy. No sklearn, no ML.
"""

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
@dataclass
class SpatialConfig:
    """
    Configuration for the spatial consistency analysis.

    Every threshold here is an OPERATIONAL HEURISTIC. None of these
    values are WMO or any other formal standard. They are sensible
    defaults for a prototype; every field is configurable so the system
    can be adapted per network, climate regime, or station density
    without editing code.

    Isolated-deviation check (STEP 16+): uses STATION-NORMALIZED
    z-scores instead of raw values, so stations with different
    baselines (e.g. AWS_03 is warmer/drier by default) can be compared
    fairly. SPATIAL_Z_TOL is the z-score tolerance; the deprecated
    SPATIAL_*_TOL fields are retained for backward compatibility but
    are no longer read by the isolated check.
    """

    # ---- Neighbourhood definition ----
    MAX_DISTANCE_KM: float = 100.0       # haversine distance filter (applied first)
    MAX_NEIGHBOURS: int | None = 2   # optional cap (None = no cap, applied AFTER distance)
    MIN_NEIGHBOURS: int = 2               # need this many valid neighbours to evaluate

    # ---- Timestamp alignment (join tolerance) ----
    TIME_TOLERANCE_MINUTES: int = 30

    # ---- Isolated-deviation threshold (z-score based, STEP 16) ----
    # Flag as isolated if the target's z-score differs from the neighbour
    # median z-score by more than this AND the target z-score is outside
    # the neighbour z-score envelope. This is an OPERATIONAL HEURISTIC,
    # not a formal standard.
    SPATIAL_Z_TOL: float = 4.5

    # DEPRECATED (kept for backward compatibility only).
    # The isolated-deviation check no longer reads these - it uses
    # SPATIAL_Z_TOL above with station-normalized z-scores instead.
    # The old names suggested "any raw deviation above this is suspicious",
    # which failed on networks with different station-specific baselines.
    SPATIAL_TEMP_TOL: float = 7.0         # DEPRECATED
    SPATIAL_PRESSURE_TOL: float = 3.0      # DEPRECATED
    SPATIAL_HUMIDITY_TOL: float = 15.0     # DEPRECATED

    # ---- Multi-station-event thresholds ----
    COMMON_EVENT_WINDOW_SAMPLES: int = 3   # look-back window in samples
    COMMON_EVENT_TEMP_MIN: float = 3.0     # deg C
    COMMON_EVENT_PRESSURE_MIN: float = 2.0 # hPa
    COMMON_EVENT_HUMIDITY_MIN: float = 10.0 # %
    COMMON_EVENT_AGREEMENT_TOL: float = 0.5 # |target_d - neigh_median_d| < tol


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
DEFAULT_METADATA_PATH = "data/station_metadata.csv"
DEFAULT_NORMAL_CSV = "data/normal_aws_data.csv"
BASELINE_EPS = 1e-6  # guard against zero-variance stations in z-score denominators

REQUIRED_META_COLUMNS = ["station_id", "latitude", "longitude"]
REQUIRED_OBS_COLUMNS = ["station_id", "timestamp", "temperature", "pressure", "humidity"]

OUTPUT_COLUMNS = [
    "spatial_neighbours_n",
    "spatial_isolated_flag",
    "spatial_isolated_reason",
    "spatial_common_event_flag",
    "spatial_common_event_reason",
    "spatial_any_flag",
    "spatial_reasons",
]


# ----------------------------------------------------------------------
# Haversine distance
# ----------------------------------------------------------------------
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points (WGS84)."""
    R = 6371.0088  # Earth's mean radius in km.
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = (np.sin(dphi / 2.0) ** 2
         + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2)
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return float(R * c)


# ----------------------------------------------------------------------
# Neighbour graph
# ----------------------------------------------------------------------
def _build_neighbour_graph(metadata_df: pd.DataFrame,
                           config: SpatialConfig) -> dict:
    """
    Build the neighbour graph.

    For each station S:
      1. Candidate neighbours = all other stations whose haversine
         distance to S is <= MAX_DISTANCE_KM.
      2. Sort candidates by distance ascending.
      3. If MAX_NEIGHBOURS is not None, truncate to the first
         MAX_NEIGHBOURS candidates.

    The distance filter is applied FIRST. MAX_NEIGHBOURS is a secondary
    cap applied AFTER distance filtering and sorting.

    Returns
    -------
    dict
        {station_id: [(neighbour_id, distance_km), ...]}
    """
    stations = metadata_df["station_id"].tolist()
    lats = metadata_df["latitude"].to_numpy(dtype=float)
    lons = metadata_df["longitude"].to_numpy(dtype=float)

    graph = {}
    for i, sid in enumerate(stations):
        candidates = []
        for j, other_sid in enumerate(stations):
            if i == j:
                continue
            dist = _haversine_km(lats[i], lons[i], lats[j], lons[j])
            if dist <= config.MAX_DISTANCE_KM:
                candidates.append((other_sid, dist))
        # Step 2: sort by distance ascending.
        candidates.sort(key=lambda x: x[1])
        # Step 3: optional cap, applied AFTER distance filtering + sorting.
        if config.MAX_NEIGHBOURS is not None:
            candidates = candidates[: config.MAX_NEIGHBOURS]
        graph[sid] = candidates
    return graph


def _print_neighbour_graph(graph: dict,
                           metadata_df: pd.DataFrame,
                           config: SpatialConfig) -> None:
    """Print the neighbour graph once at startup, with distance stats."""
    print("-" * 70)
    print("Neighbour graph")
    print("-" * 70)
    print(f"MAX_DISTANCE_KM = {config.MAX_DISTANCE_KM}")
    print(f"MAX_NEIGHBOURS  = {config.MAX_NEIGHBOURS}")
    print(f"MIN_NEIGHBOURS  = {config.MIN_NEIGHBOURS}")
    print()

    # All pairwise distances (for stats so the reader can judge whether
    # MAX_DISTANCE_KM is meaningful for this dataset).
    all_dists = []
    stations = metadata_df["station_id"].tolist()
    lats = metadata_df["latitude"].to_numpy(dtype=float)
    lons = metadata_df["longitude"].to_numpy(dtype=float)
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            d = _haversine_km(lats[i], lons[i], lats[j], lons[j])
            all_dists.append(d)
    if all_dists:
        print(f"Inter-station distance (km): "
              f"min={min(all_dists):.2f}, "
              f"median={float(np.median(all_dists)):.2f}, "
              f"max={max(all_dists):.2f}")
        print(f"(MAX_DISTANCE_KM={config.MAX_DISTANCE_KM} "
              f"{'includes' if max(all_dists) <= config.MAX_DISTANCE_KM else 'filters out some pairs of'} "
              f"all pairs in this network)")
    print()

    for sid in sorted(graph.keys()):
        neighbours = graph[sid]
        if not neighbours:
            print(f"  {sid}: no neighbours within {config.MAX_DISTANCE_KM} km "
                  f"(insufficient spatial context)")
        else:
            neigh_str = ", ".join([f"{n} ({d:.2f} km)" for n, d in neighbours])
            print(f"  {sid}: {len(neighbours)} neighbour(s): {neigh_str}")
    print("-" * 70)


# ----------------------------------------------------------------------
# Station baselines (training data only, no leakage)
# ----------------------------------------------------------------------
def _compute_station_baselines(normal_csv: str, station_ids: list) -> dict:
    """
    Compute per-station, per-variable (mean, std) baselines from
    TRAINING data only (data/normal_aws_data.csv), never the test set.

    For each station and each of {temperature, pressure, humidity},
    computes mean and std over that station's own training observations.
    Uses BASELINE_EPS in std denominators to guard against zero-variance
    stations.

    Returns
    -------
    dict
        {station_id: {var: (mean, std), ...}, ...}
        Also includes a special key "__global__" with global mean/std per
        variable, used as fallback for stations missing from the training
        data.
    """
    if not os.path.exists(normal_csv):
        raise FileNotFoundError(
            f"Normal training data not found: {normal_csv}. "
            "The z-score isolated-deviation check requires baseline "
            "statistics computed from the normal training data."
        )

    df = pd.read_csv(normal_csv)

    # Per-station baselines.
    baselines = {}
    for sid, g in df.groupby("station_id"):
        baselines[sid] = {}
        for var in ["temperature", "pressure", "humidity"]:
            if var not in g.columns:
                continue
            vals = g[var].dropna()
            if len(vals) > 0:
                mean = float(vals.mean())
                std = float(vals.std())
                if np.isnan(std) or std == 0:
                    std = BASELINE_EPS
                baselines[sid][var] = (mean, std)

    # Global baselines (fallback for stations missing from training data).
    global_baselines = {}
    for var in ["temperature", "pressure", "humidity"]:
        if var not in df.columns:
            continue
        vals = df[var].dropna()
        if len(vals) > 0:
            mean = float(vals.mean())
            std = float(vals.std())
            if np.isnan(std) or std == 0:
                std = BASELINE_EPS
            global_baselines[var] = (mean, std)
    baselines["__global__"] = global_baselines

    return baselines


def _get_baseline_params(baselines: dict, station_id: str,
                         var: str) -> tuple:
    """
    Returns (mu, sd, is_fallback) for the given station and variable.

    If the station is missing from the training data, falls back to the
    global mean/std and sets is_fallback = True.
    """
    if station_id in baselines and var in baselines[station_id]:
        mu, sd = baselines[station_id][var]
        return mu, sd, False
    # Fall back to global.
    global_baselines = baselines.get("__global__", {})
    if var in global_baselines:
        mu, sd = global_baselines[var]
        return mu, sd, True
    return 0.0, BASELINE_EPS, True


# ----------------------------------------------------------------------
# Spatial analysis (per-row, per-station)
# ----------------------------------------------------------------------
def apply_spatial_analysis(observations_df: pd.DataFrame,
                          metadata_df: pd.DataFrame,
                          config: SpatialConfig | None = None,
                          baselines: dict | None = None) -> pd.DataFrame:
    """
    Apply spatial consistency analysis to AWS observations.

    Parameters
    ----------
    observations_df : pd.DataFrame
        Raw AWS observations. Must contain at minimum:
        station_id, timestamp, temperature, pressure, humidity.
        Does NOT require d_* features and does NOT call feature_engineering.
    metadata_df : pd.DataFrame
        Station metadata. Must contain at minimum:
        station_id, latitude, longitude.
    config : SpatialConfig | None
        Optional configuration. Defaults to SpatialConfig().
    baselines : dict | None
        Optional pre-computed station baselines (output of
        _compute_station_baselines). If None, the function loads them
        internally from data/normal_aws_data.csv. Stations missing from
        the training data fall back to global mean/std; the reason string
        notes "(baseline fallback)" when this happens.

    Returns
    -------
    pd.DataFrame
        Copy of observations_df with these columns ADDED:
          spatial_neighbours_n, spatial_isolated_flag,
          spatial_isolated_reason, spatial_common_event_flag,
          spatial_common_event_reason, spatial_any_flag,
          spatial_reasons.
        The input is NOT mutated. Output is joinable with
        isolation_forest_predictions.csv and QC flags by
        (station_id, timestamp).
    """
    if config is None:
        config = SpatialConfig()

    # Load baselines if not provided (TRAINING data only, no leakage).
    if baselines is None:
        station_ids = metadata_df["station_id"].tolist()
        baselines = _compute_station_baselines(DEFAULT_NORMAL_CSV, station_ids)

    # Validate metadata.
    missing_meta = [c for c in REQUIRED_META_COLUMNS if c not in metadata_df.columns]
    if missing_meta:
        raise ValueError(
            f"Station metadata missing required columns: {missing_meta}. "
            f"Required: {REQUIRED_META_COLUMNS}."
        )

    # Validate observations.
    missing_obs = [c for c in REQUIRED_OBS_COLUMNS if c not in observations_df.columns]
    if missing_obs:
        raise ValueError(
            f"Observations missing required columns: {missing_obs}. "
            f"Required: {REQUIRED_OBS_COLUMNS}."
        )

    # Build the neighbour graph ONCE.
    graph = _build_neighbour_graph(metadata_df, config)
    # Print it once at startup (per spec).
    _print_neighbour_graph(graph, metadata_df, config)

    # Work on a copy; do NOT mutate input.
    out = observations_df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out = out[out["timestamp"].notna()].copy()
    out = out.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    # Initialize output columns.
    n_out = len(out)
    spatial_neighbours_n = np.zeros(n_out, dtype=int)
    spatial_isolated_flag = np.zeros(n_out, dtype=int)
    spatial_isolated_reason = np.array([""] * n_out, dtype=object)
    spatial_common_event_flag = np.zeros(n_out, dtype=int)
    spatial_common_event_reason = np.array([""] * n_out, dtype=object)
    spatial_any_flag = np.zeros(n_out, dtype=int)
    spatial_reasons = np.array([""] * n_out, dtype=object)

    # Pre-compute look-back features for the common-event check.
    # d_x = x[t] - x[t - COMMON_EVENT_WINDOW_SAMPLES], per station.
    # First COMMON_EVENT_WINDOW_SAMPLES rows of each station have NaN look-back
    # (no fill - we do NOT inject a fake "no change" signal). The common-event
    # check skips rows where target_d is NaN.
    lb_window = config.COMMON_EVENT_WINDOW_SAMPLES
    lb_cols = {}
    for var in ["temperature", "pressure", "humidity"]:
        lb_col = f"_lb_{var}"
        out[lb_col] = out.groupby("station_id")[var].diff(lb_window)
        lb_cols[var] = lb_col

    # Pre-build per-station observation frames (sorted by timestamp) for
    # efficient merge_asof lookups. O(n log n) per station, done once.
    station_dfs = {}
    for sid, gdf in out.groupby("station_id"):
        sdf = gdf.sort_values("timestamp")[
            ["timestamp", "temperature", "pressure", "humidity",
             lb_cols["temperature"], lb_cols["pressure"], lb_cols["humidity"]]
        ].copy()
        station_dfs[sid] = sdf

    time_tol = pd.Timedelta(minutes=config.TIME_TOLERANCE_MINUTES)

    # Process each target station.
    for target_sid, target_group in out.groupby("station_id"):
        # Sorted-by-timestamp view (already sorted, but explicit for clarity).
        target_df = target_group.sort_values("timestamp")
        target_indices = target_df.index.to_numpy()  # positions in `out`
        n_target = len(target_df)

        neighbours = graph.get(target_sid, [])

        # Insufficient spatial context: flags stay 0, reason notes it.
        if len(neighbours) < config.MIN_NEIGHBOURS:
            reason = (f"insufficient spatial context "
                      f"(n_neighbours={len(neighbours)}, "
                      f"min_required={config.MIN_NEIGHBOURS})")
            for idx in target_indices:
                spatial_reasons[idx] = reason
            continue

        n_neighbours = len(neighbours)

        # For each neighbour, use merge_asof to find the nearest observation
        # per target row within the time tolerance. O(n_target log n_neighbour)
        # per (target, neighbour) pair.
        # We collect each neighbour's matched values into numpy arrays.
        neigh_t = np.full((n_neighbours, n_target), np.nan)
        neigh_p = np.full((n_neighbours, n_target), np.nan)
        neigh_h = np.full((n_neighbours, n_target), np.nan)
        neigh_dt = np.full((n_neighbours, n_target), np.nan)
        neigh_dp = np.full((n_neighbours, n_target), np.nan)
        neigh_dh = np.full((n_neighbours, n_target), np.nan)

        target_keys = target_df[["timestamp"]].copy()  # already sorted

        for k, (neigh_sid, _dist) in enumerate(neighbours):
            if neigh_sid not in station_dfs:
                continue
            neigh_sdf = station_dfs[neigh_sid]
            merged = pd.merge_asof(
                target_keys,
                neigh_sdf,
                on="timestamp",
                tolerance=time_tol,
                direction="nearest",
            )
            neigh_t[k] = merged["temperature"].to_numpy(dtype=float)
            neigh_p[k] = merged["pressure"].to_numpy(dtype=float)
            neigh_h[k] = merged["humidity"].to_numpy(dtype=float)
            neigh_dt[k] = merged[lb_cols["temperature"]].to_numpy(dtype=float)
            neigh_dp[k] = merged[lb_cols["pressure"]].to_numpy(dtype=float)
            neigh_dh[k] = merged[lb_cols["humidity"]].to_numpy(dtype=float)

        # Target's own values.
        target_t = target_df["temperature"].to_numpy(dtype=float)
        target_p = target_df["pressure"].to_numpy(dtype=float)
        target_h = target_df["humidity"].to_numpy(dtype=float)
        target_dt = target_df[lb_cols["temperature"]].to_numpy(dtype=float)
        target_dp = target_df[lb_cols["pressure"]].to_numpy(dtype=float)
        target_dh = target_df[lb_cols["humidity"]].to_numpy(dtype=float)

        # ---- Precompute z-score arrays for the isolated-deviation check ----
        # Z-scores normalize each station's reading by its own baseline
        # (mean, std) computed from the training data. This lets us compare
        # stations with different baselines fairly: a temperature of 25 C
        # at AWS_03 (mean=25) is z=0, while 25 C at AWS_01 (mean=22) is z≈1.
        eps = BASELINE_EPS
        neigh_sids = [n[0] for n in neighbours]

        # Per-neighbour baseline params: arrays of mu, sd, is_fallback.
        neigh_mu_t = np.array([_get_baseline_params(baselines, s, "temperature")[0] for s in neigh_sids])
        neigh_sd_t = np.array([max(_get_baseline_params(baselines, s, "temperature")[1], eps) for s in neigh_sids])
        neigh_fb_t = np.array([_get_baseline_params(baselines, s, "temperature")[2] for s in neigh_sids])
        neigh_mu_p = np.array([_get_baseline_params(baselines, s, "pressure")[0] for s in neigh_sids])
        neigh_sd_p = np.array([max(_get_baseline_params(baselines, s, "pressure")[1], eps) for s in neigh_sids])
        neigh_fb_p = np.array([_get_baseline_params(baselines, s, "pressure")[2] for s in neigh_sids])
        neigh_mu_h = np.array([_get_baseline_params(baselines, s, "humidity")[0] for s in neigh_sids])
        neigh_sd_h = np.array([max(_get_baseline_params(baselines, s, "humidity")[1], eps) for s in neigh_sids])
        neigh_fb_h = np.array([_get_baseline_params(baselines, s, "humidity")[2] for s in neigh_sids])

        # Neighbour z-score arrays (same shape as neigh_t etc.).
        # neigh_z_t[k, i] = (neigh_t[k, i] - neigh_mu_t[k]) / neigh_sd_t[k]
        neigh_z_t = (neigh_t - neigh_mu_t[:, None]) / neigh_sd_t[:, None]
        neigh_z_p = (neigh_p - neigh_mu_p[:, None]) / neigh_sd_p[:, None]
        neigh_z_h = (neigh_h - neigh_mu_h[:, None]) / neigh_sd_h[:, None]

        # Target baseline params and z-scores.
        t_mu, t_sd, t_fb = _get_baseline_params(baselines, target_sid, "temperature")
        p_mu, p_sd, p_fb = _get_baseline_params(baselines, target_sid, "pressure")
        h_mu, h_sd, h_fb = _get_baseline_params(baselines, target_sid, "humidity")
        t_sd, p_sd, h_sd = max(t_sd, eps), max(p_sd, eps), max(h_sd, eps)
        target_z_t = (target_t - t_mu) / t_sd
        target_z_p = (target_p - p_mu) / p_sd
        target_z_h = (target_h - h_mu) / h_sd

        # Per-row evaluation: O(k) per row where k = n_neighbours.
        for i in range(n_target):
            idx = target_indices[i]

            # Valid neighbour values per variable (NaN excluded).
            t_vals = neigh_t[:, i]
            p_vals = neigh_p[:, i]
            h_vals = neigh_h[:, i]
            t_valid = t_vals[~np.isnan(t_vals)]
            p_valid = p_vals[~np.isnan(p_vals)]
            h_valid = h_vals[~np.isnan(h_vals)]

            # spatial_neighbours_n: number of neighbours with a valid
            # observation for at least one variable at this row.
            any_valid = (~np.isnan(t_vals)) | (~np.isnan(p_vals)) | (~np.isnan(h_vals))
            spatial_neighbours_n[idx] = int(any_valid.sum())

            isolated_reasons = []
            common_reasons = []
            isolated_vars = set()
            common_vars = set()

            # ---- ISOLATED DEVIATION CHECK (z-score based, STEP 16) ----
            # Flag if BOTH |deviation_z| > SPATIAL_Z_TOL
            # AND target_z outside [z_min, z_max].
            # Uses station-normalized z-scores so stations with different
            # baselines can be compared fairly.
            for var_label, var_short, target_val, target_z, \
                neigh_vals, neigh_zs, neigh_fb_arr, target_fb in [
                ("temperature", "T", target_t[i], target_z_t[i],
                 neigh_t[:, i], neigh_z_t[:, i], neigh_fb_t, t_fb),
                ("pressure",    "P", target_p[i], target_z_p[i],
                 neigh_p[:, i], neigh_z_p[:, i], neigh_fb_p, p_fb),
                ("humidity",    "RH", target_h[i], target_z_h[i],
                 neigh_h[:, i], neigh_z_h[:, i], neigh_fb_h, h_fb),
            ]:
                if np.isnan(target_val) or np.isnan(target_z):
                    continue
                # Valid neighbour values: both raw and z-score must be non-NaN.
                valid_mask = (~np.isnan(neigh_vals)) & (~np.isnan(neigh_zs))
                if valid_mask.sum() < config.MIN_NEIGHBOURS:
                    continue
                valid_raw = neigh_vals[valid_mask]
                valid_zs = neigh_zs[valid_mask]
                z_median = float(np.median(valid_zs))
                z_min = float(np.min(valid_zs))
                z_max = float(np.max(valid_zs))
                deviation_z = target_z - z_median
                if abs(deviation_z) > config.SPATIAL_Z_TOL \
                        and (target_z < z_min or target_z > z_max):
                    # Check if any station (target or neighbour) used fallback.
                    any_fallback = bool(target_fb) or bool(np.any(neigh_fb_arr[valid_mask]))
                    # Build reason string with BOTH raw values AND z-scores.
                    neigh_str = ", ".join([
                        f"{rv:.1f} (z={rz:.1f})"
                        for rv, rz in zip(valid_raw, valid_zs)
                    ])
                    reason = (
                        f"isolated spatial anomaly: {var_label}="
                        f"{target_val:.1f} (z={target_z:.1f}) vs neighbours "
                        f"[{neigh_str}] "
                        f"(median z={z_median:.1f}, n={len(valid_zs)})"
                    )
                    if any_fallback:
                        reason += " (baseline fallback)"
                    isolated_reasons.append(reason)
                    isolated_vars.add(var_short)

            # ---- COMMON EVENT CHECK (per variable) ----
            # Flag if |median neighbour d_x| > COMMON_EVENT_*_MIN
            # AND target's own d_x is within COMMON_EVENT_AGREEMENT_TOL of
            # the neighbour median d_x.
            for var_label, var_short, target_d, neigh_d_col, common_min in [
                ("temperature", "T", target_dt[i], neigh_dt[:, i], config.COMMON_EVENT_TEMP_MIN),
                ("pressure",    "P", target_dp[i], neigh_dp[:, i], config.COMMON_EVENT_PRESSURE_MIN),
                ("humidity",    "RH", target_dh[i], neigh_dh[:, i], config.COMMON_EVENT_HUMIDITY_MIN),
            ]:
                if np.isnan(target_d):
                    continue  # first-row-per-station or insufficient history
                d_valid = neigh_d_col[~np.isnan(neigh_d_col)]
                if len(d_valid) < config.MIN_NEIGHBOURS:
                    continue
                neigh_d_median = float(np.median(d_valid))
                if (abs(neigh_d_median) > common_min
                        and abs(target_d - neigh_d_median) < config.COMMON_EVENT_AGREEMENT_TOL):
                    common_reasons.append(
                        f"common event: {var_label} change {target_d:.1f} "
                        f"matches neighbourhood median {neigh_d_median:.1f} "
                        f"(n={len(d_valid)})"
                    )
                    common_vars.add(var_short)

            # ---- Flags ----
            iso_flag = 1 if isolated_reasons else 0
            com_flag = 1 if common_reasons else 0
            any_flag = 1 if (iso_flag or com_flag) else 0

            isolated_reason_str = "; ".join(isolated_reasons)
            common_reason_str = "; ".join(common_reasons)

            # ---- Contradiction: both flags for same variable ----
            contradiction_vars = isolated_vars & common_vars
            contradiction_note = ""
            if contradiction_vars:
                contradiction_note = (
                    "note: both isolated deviation and common event detected "
                    f"for {sorted(contradiction_vars)}"
                )

            # Aggregate spatial_reasons: " | " joined reasons + note.
            all_reasons = isolated_reasons + common_reasons
            if contradiction_note:
                all_reasons.append(contradiction_note)
            reasons_str = " | ".join(all_reasons) if all_reasons else ""

            # Write to arrays (much faster than .at per-row).
            spatial_isolated_flag[idx] = iso_flag
            spatial_isolated_reason[idx] = isolated_reason_str
            spatial_common_event_flag[idx] = com_flag
            spatial_common_event_reason[idx] = common_reason_str
            spatial_any_flag[idx] = any_flag
            spatial_reasons[idx] = reasons_str

    # Assign collected arrays back to the output DataFrame.
    out["spatial_neighbours_n"] = spatial_neighbours_n
    out["spatial_isolated_flag"] = spatial_isolated_flag
    out["spatial_isolated_reason"] = spatial_isolated_reason
    out["spatial_common_event_flag"] = spatial_common_event_flag
    out["spatial_common_event_reason"] = spatial_common_event_reason
    out["spatial_any_flag"] = spatial_any_flag
    out["spatial_reasons"] = spatial_reasons

    # Drop temporary look-back columns (don't leak them into the output).
    out = out.drop(columns=list(lb_cols.values()))

    return out


# ----------------------------------------------------------------------
# Demo (with REQUIRED diagnostic cross-checks)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("SkyGuard AI - STEP 15: Spatial Consistency Analysis (demo)")
    print("=" * 70)

    # 1. Load metadata.
    metadata_path = DEFAULT_METADATA_PATH
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(
            f"Station metadata file not found: {metadata_path}. "
            "The spatial analysis requires station coordinates "
            "(station_id, latitude, longitude). Please create this file."
        )
    metadata_df = pd.read_csv(metadata_path)
    print(f"\nLoaded metadata: {len(metadata_df)} stations from {metadata_path}")

    # 2. Load observations (raw, no feature engineering required).
    obs_path = "data/test_injected_aws.csv"
    if not os.path.exists(obs_path):
        raise FileNotFoundError(f"Observations file not found: {obs_path}.")
    obs_df = pd.read_csv(obs_path)
    print(f"Loaded observations: {len(obs_df)} rows from {obs_path}\n")

    # 3. Compute and print station baselines (from TRAINING data only).
    station_ids = metadata_df["station_id"].tolist()
    baselines = _compute_station_baselines(DEFAULT_NORMAL_CSV, station_ids)
    print()
    print("=" * 70)
    print("Computed baselines (from data/normal_aws_data.csv, TRAINING only)")
    print("=" * 70)
    for sid in sorted(station_ids):
        for var in ["temperature", "pressure", "humidity"]:
            mu, sd, is_fb = _get_baseline_params(baselines, sid, var)
            fb_note = " (global fallback)" if is_fb else ""
            print(f"  {sid} {var:11s}: mean={mu:7.2f}  std={sd:6.2f}{fb_note}")
    # Also print global baselines for reference.
    print("  ---")
    for var in ["temperature", "pressure", "humidity"]:
        if "__global__" in baselines and var in baselines["__global__"]:
            g_mu, g_sd = baselines["__global__"][var]
            print(f"  {'GLOBAL':10s} {var:11s}: mean={g_mu:7.2f}  std={g_sd:6.2f}")

    # 3b. Run spatial analysis with baselines.
    result = apply_spatial_analysis(obs_df, metadata_df, baselines=baselines)

    # 4. Print summary.
    print(f"\nTotal rows analysed: {len(result)}")
    print()
    print("spatial_isolated_flag counts:")
    print(result["spatial_isolated_flag"].value_counts().to_string())
    print()
    print("spatial_common_event_flag counts:")
    print(result["spatial_common_event_flag"].value_counts().to_string())
    print()
    print("Per-station breakdown of spatial_isolated_flag:")
    per_station = result.groupby("station_id")["spatial_isolated_flag"].agg(["sum", "count"])
    per_station.columns = ["n_flagged", "n_total"]
    print(per_station.to_string())

    # 5. DIAGNOSTIC CROSS-CHECKS (REQUIRED, not optional).
    print()
    print("=" * 70)
    print("DIAGNOSTIC CROSS-CHECKS (vs ground-truth is_anomaly)")
    print("=" * 70)
    if "is_anomaly" not in result.columns or result["is_anomaly"].isna().all():
        print("[NOTE] is_anomaly not available in input; cross-checks skipped.")
    else:
        n_iso_anom = int(((result["spatial_isolated_flag"] == 1) & (result["is_anomaly"] == 1)).sum())
        n_iso_norm = int(((result["spatial_isolated_flag"] == 1) & (result["is_anomaly"] == 0)).sum())
        n_com_norm = int(((result["spatial_common_event_flag"] == 1) & (result["is_anomaly"] == 0)).sum())
        n_com_anom = int(((result["spatial_common_event_flag"] == 1) & (result["is_anomaly"] == 1)).sum())

        print(f"(a) spatial_isolated_flag=1 AND is_anomaly=1   : {n_iso_anom}")
        print(f"(b) spatial_isolated_flag=1 AND is_anomaly=0   : {n_iso_norm}  (spatial false alarms - expected low)")
        print(f"(c) spatial_common_event_flag=1 AND is_anomaly=0: {n_com_norm}")
        print(f"(d) spatial_common_event_flag=1 AND is_anomaly=1: {n_com_anom}  (spatial false negatives - expected low but nonzero)")

        # (e) Per anomaly_type breakdown.
        if "anomaly_type" in result.columns:
            print()
            print("Per anomaly_type breakdown:")
            header = (f"  {'anomaly_type':<30s}  "
                      f"{'(a) iso&anom':>14s}  "
                      f"{'(b) iso&norm':>14s}  "
                      f"{'(c) com&norm':>14s}  "
                      f"{'(d) com&anom':>14s}")
            print(header)
            print("  " + "-" * (len(header) - 2))
            for atype, g in result.groupby("anomaly_type"):
                a = int(((g["spatial_isolated_flag"] == 1) & (g["is_anomaly"] == 1)).sum())
                b = int(((g["spatial_isolated_flag"] == 1) & (g["is_anomaly"] == 0)).sum())
                c = int(((g["spatial_common_event_flag"] == 1) & (g["is_anomaly"] == 0)).sum())
                d = int(((g["spatial_common_event_flag"] == 1) & (g["is_anomaly"] == 1)).sum())
                print(f"  {str(atype):<30s}  {a:>14d}  {b:>14d}  {c:>14d}  {d:>14d}")

    # 6. Top 5 rows by spatial_isolated_flag with reasons.
    print()
    print("=" * 70)
    print("Top 5 rows with spatial_isolated_flag=1 (with reasons)")
    print("=" * 70)
    iso_rows = result[result["spatial_isolated_flag"] == 1].head(5)
    if iso_rows.empty:
        print("(no rows with spatial_isolated_flag=1)")
    else:
        cols = ["timestamp", "station_id", "temperature", "pressure", "humidity",
                "spatial_isolated_reason"]
        for line in iso_rows[cols].to_string(index=False, max_colwidth=120).splitlines():
            print("  " + line)

    # 7. BEFORE/AFTER COMPARISON (STEP 15 raw vs STEP 16 z-score).
    print()
    print("=" * 70)
    print("BEFORE/AFTER COMPARISON")
    print("=" * 70)
    # STEP 15 numbers are from the previous run (tol=7.0 raw comparison).
    print("STEP 15 baseline (tol=7.0 raw): isolated = 2,865, "
          "isolated&anomaly = 50, isolated&normal = 2,815")
    # STEP 16 numbers are computed from the current z-score run.
    n_iso_step16 = int(result["spatial_isolated_flag"].sum())
    if "is_anomaly" in result.columns and not result["is_anomaly"].isna().all():
        n_iso_anom_step16 = int(
            ((result["spatial_isolated_flag"] == 1) & (result["is_anomaly"] == 1)).sum()
        )
        n_iso_norm_step16 = int(
            ((result["spatial_isolated_flag"] == 1) & (result["is_anomaly"] == 0)).sum()
        )
    else:
        n_iso_anom_step16 = 0
        n_iso_norm_step16 = 0
    print(f"STEP 16 (z-score):           isolated = {n_iso_step16}, "
          f"isolated&anomaly = {n_iso_anom_step16}, "
          f"isolated&normal = {n_iso_norm_step16}")
    if n_iso_step16 >= 2865:
        print("[NOTE] Isolated flags did not decrease. The z-score test "
              "may need SPATIAL_Z_TOL tuning, or the baseline mismatch "
              "is larger than expected.")