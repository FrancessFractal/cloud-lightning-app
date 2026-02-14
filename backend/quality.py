"""Data quality assessment for location-based weather estimates.

Uses a report-card model: four independent factors are each graded
good / fair / poor, and the overall level equals the worst factor.

Factors:
  1. Data coverage — % of time buckets with any observations
  2. Observation depth — obs count vs expected baseline for the resolution
  3. Station proximity — weighted average distance of contributing stations
  4. Directional coverage — angular spread of stations around the target
"""

import math

# ---------------------------------------------------------------------------
# Expected observations per data point for "well-covered" data
# ---------------------------------------------------------------------------

_GOOD_OBS = {
    "day": 30,
    "month": 500,
    "year": 2000,
}

# ---------------------------------------------------------------------------
# Thresholds for each factor → good / fair / poor
# ---------------------------------------------------------------------------

_COVERAGE_GOOD = 90   # %
_COVERAGE_FAIR = 60

_DEPTH_GOOD = 70      # %
_DEPTH_FAIR = 40

_PROX_GOOD_KM = 25    # km
_PROX_FAIR_KM = 75

_DIR_GOOD_DEG = 180   # degrees of angular spread
_DIR_FAIR_DEG = 90

_LEVEL_ORDER = {"poor": 0, "fair": 1, "good": 2}
_LEVEL_MAP = {0: "low", 1: "medium", 2: "high"}

# ---------------------------------------------------------------------------
# Empty quality result (used when no data is available)
# ---------------------------------------------------------------------------

EMPTY_QUALITY: dict = {
    "level": "low",
    "coverage": {"value": 0, "level": "poor"},
    "depth": {"value": 0, "level": "poor"},
    "proximity": {"value": 0, "level": "poor", "avg_km": None},
    "direction": {"value": 0, "level": "poor", "spread_deg": 0},
    "median_obs": 0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify(value, good_thresh, fair_thresh, higher_is_better=True):
    """Return 'good', 'fair', or 'poor' based on thresholds."""
    if higher_is_better:
        if value >= good_thresh:
            return "good"
        if value >= fair_thresh:
            return "fair"
        return "poor"
    else:
        # Lower is better (e.g. distance)
        if value <= good_thresh:
            return "good"
        if value <= fair_thresh:
            return "fair"
        return "poor"


def _bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute the initial compass bearing (0-360) from point 1 to point 2."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    d_lng = math.radians(lng2 - lng1)
    x = math.sin(d_lng) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - (
        math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lng)
    )
    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


def _angular_spread(bearings: list[float]) -> float:
    """Compute the minimum arc (degrees) that contains all bearings.

    Returns 0 for 0-1 bearings, up to 360 for perfectly surrounding stations.
    """
    if len(bearings) <= 1:
        return 0.0
    s = sorted(b % 360 for b in bearings)
    # Compute gaps between consecutive bearings (including wraparound)
    max_gap = 0.0
    for i in range(len(s) - 1):
        gap = s[i + 1] - s[i]
        if gap > max_gap:
            max_gap = gap
    # Wraparound gap
    wrap_gap = (360 - s[-1]) + s[0]
    if wrap_gap > max_gap:
        max_gap = wrap_gap
    return round(360 - max_gap, 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_quality(
    points: list[dict],
    resolution: str,
    station_data: list[dict],
    target_lat: float,
    target_lng: float,
) -> dict:
    """Compute a report-card data quality assessment.

    Each of four factors gets an independent level (good / fair / poor).
    The overall level equals the worst individual factor.

    Parameters
    ----------
    points : list[dict]
        Blended data points (must have ``obs_count``).
    resolution : str
        ``"day"``, ``"month"``, or ``"year"``.
    station_data : list[dict]
        Selected stations with ``station`` and ``weight`` keys.
    target_lat, target_lng : float
        The location the user searched for.

    Returns
    -------
    dict with per-factor breakdowns and an overall ``level``.
    """
    total_pts = len(points)
    if total_pts == 0:
        return dict(EMPTY_QUALITY)

    # --- 1. Coverage: % of points with any data ---
    obs_counts = [p.get("obs_count", 0) for p in points]
    coverage_val = round(
        sum(1 for o in obs_counts if o > 0) / total_pts * 100, 1
    )
    coverage_level = _classify(coverage_val, _COVERAGE_GOOD, _COVERAGE_FAIR)

    # --- 2. Depth: observation depth vs expected baseline ---
    good_baseline = _GOOD_OBS.get(resolution, 500)
    per_point = [min(o / good_baseline, 1.0) for o in obs_counts]
    depth_val = round(sum(per_point) / total_pts * 100, 1)
    depth_level = _classify(depth_val, _DEPTH_GOOD, _DEPTH_FAIR)

    # Median obs
    sorted_obs = sorted(obs_counts)
    mid = total_pts // 2
    median_obs = (
        sorted_obs[mid]
        if total_pts % 2 == 1
        else (sorted_obs[mid - 1] + sorted_obs[mid]) // 2
    )

    # --- 3. Proximity: weighted average distance ---
    avg_dist = sum(
        sd["station"]["distance_km"] * sd["weight"] for sd in station_data
    )
    avg_km = round(avg_dist, 1)
    # Map to a 0-100 score for the progress bar
    prox_val = max(0.0, min(100.0, round(
        (1 - min(avg_dist, 200) / 200) * 100, 1
    )))
    prox_level = _classify(
        avg_dist, _PROX_GOOD_KM, _PROX_FAIR_KM, higher_is_better=False
    )

    # --- 4. Directional coverage: angular spread of stations ---
    bearings = [
        _bearing(
            target_lat, target_lng,
            sd["station"]["latitude"], sd["station"]["longitude"],
        )
        for sd in station_data
    ]
    spread = _angular_spread(bearings)
    # Map to 0-100 for progress bar (0 deg → 0, 360 deg → 100)
    dir_val = round(min(spread / 360, 1.0) * 100, 1)
    dir_level = _classify(spread, _DIR_GOOD_DEG, _DIR_FAIR_DEG)

    # --- Overall: worst individual factor ---
    # Exception: when stations are close (proximity good), directional
    # coverage matters much less — you're reading a nearby station, not
    # interpolating across a wide region.  Upgrade direction to at least
    # "fair" in that case so it doesn't drag the whole score to "low".
    effective_dir = dir_level
    if prox_level == "good" and dir_level == "poor":
        effective_dir = "fair"

    all_levels = [coverage_level, depth_level, prox_level, effective_dir]
    worst = min(_LEVEL_ORDER[lv] for lv in all_levels)
    overall = _LEVEL_MAP[worst]

    return {
        "level": overall,
        "coverage": {"value": coverage_val, "level": coverage_level},
        "depth": {"value": depth_val, "level": depth_level},
        "proximity": {"value": prox_val, "level": prox_level, "avg_km": avg_km},
        "direction": {"value": dir_val, "level": dir_level, "spread_deg": spread},
        "median_obs": median_obs,
    }
