"""Data quality assessment for location-based weather estimates.

Uses a report-card model with **independent assessments** for cloud coverage
and lightning probability.  Each dimension has its own station set and gets
two factors graded good / fair / poor:

  1. Station coverage — proximity + directional spread of that dimension's stations
  2. Historical data  — time-period coverage + observation depth

The overall quality level equals the worst factor across both dimensions.
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

_FACTOR_LEVELS = ("poor", "fair", "good")
_LEVEL_ORDER = {"poor": 0, "fair": 1, "good": 2}
_LEVEL_MAP = {0: "low", 1: "medium", 2: "high"}

# ---------------------------------------------------------------------------
# Empty quality result (used when no data is available)
# ---------------------------------------------------------------------------

_EMPTY_DIM: dict = {
    "station_coverage": {
        "value": 0,
        "level": "poor",
        "summary": "No station data available.",
    },
    "historical_data": {
        "value": 0,
        "level": "poor",
        "summary": "No historical data available.",
    },
}

EMPTY_QUALITY: dict = {
    "level": "low",
    "cloud": dict(_EMPTY_DIM),
    "lightning": dict(_EMPTY_DIM),
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
    """Compute the minimum arc (degrees) that contains all bearings."""
    if len(bearings) <= 1:
        return 0.0
    s = sorted(b % 360 for b in bearings)
    max_gap = 0.0
    for i in range(len(s) - 1):
        gap = s[i + 1] - s[i]
        if gap > max_gap:
            max_gap = gap
    wrap_gap = (360 - s[-1]) + s[0]
    if wrap_gap > max_gap:
        max_gap = wrap_gap
    return round(360 - max_gap, 1)


# ---------------------------------------------------------------------------
# Human-readable summaries
# ---------------------------------------------------------------------------

_COMPASS_NAMES = [
    "north", "north-northeast", "northeast", "east-northeast",
    "east", "east-southeast", "southeast", "south-southeast",
    "south", "south-southwest", "southwest", "west-southwest",
    "west", "west-northwest", "northwest", "north-northwest",
]


def _compass_direction(bearing: float) -> str:
    idx = round(bearing / 22.5) % 16
    return _COMPASS_NAMES[idx]


def _weighted_mean_bearing(bearings: list[float], weights: list[float]) -> float:
    sin_sum = sum(w * math.sin(math.radians(b)) for b, w in zip(bearings, weights))
    cos_sum = sum(w * math.cos(math.radians(b)) for b, w in zip(bearings, weights))
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360


def _build_station_summary(*, prox_level, dir_level, max_weight, top_name,
                           bearings, weights):
    """Plain-language explanation of station coverage."""
    parts = []

    if max_weight >= 0.85:
        parts.append(
            f"Estimates are based almost entirely on the nearby {top_name} "
            f"station, so the data is highly representative of this location."
        )
    elif prox_level == "good":
        parts.append(
            "There are stations close to this location, giving a reliable estimate."
        )
    elif prox_level == "fair":
        parts.append(
            "The nearest stations are at a moderate distance. "
            "Estimates are reasonable but may not capture very local conditions."
        )
    else:
        parts.append(
            "There are no nearby stations, so the estimates are "
            "computed from stations that are far away."
        )

    if max_weight < 0.85 and dir_level in ("poor", "fair"):
        avg_bearing = _weighted_mean_bearing(bearings, weights)
        direction_name = _compass_direction(avg_bearing)
        if dir_level == "poor":
            parts.append(
                f"These stations are all to the {direction_name} of the "
                f"location, so the estimate may not reflect conditions in "
                f"other directions."
            )
        else:
            parts.append(
                f"Most stations are to the {direction_name}, which gives "
                f"partial but not full surrounding coverage."
            )

    return " ".join(parts)


def _build_data_summary(*, coverage_pct, coverage_level, depth_level):
    """Plain-language explanation of the historical data factor."""
    parts = []

    if coverage_pct == 100:
        parts.append("Every time period has real observations.")
    elif coverage_level == "good":
        parts.append(
            "Nearly all time periods have observations, with a few small "
            "gaps filled in by estimates."
        )
    elif coverage_level == "fair":
        parts.append(
            "Some time periods are missing observations and have been "
            "filled in with estimates."
        )
    else:
        parts.append("There are significant gaps in the historical record.")

    if depth_level == "good":
        parts.append(
            "The data spans many years of consistent readings, giving "
            "reliable averages."
        )
    elif depth_level == "fair":
        parts.append(
            "The amount of data behind each average is moderate — enough "
            "to be useful, but not as precise as well-covered areas."
        )
    else:
        parts.append(
            "The number of individual readings is low, so the averages "
            "may be less precise."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Per-dimension quality assessment
# ---------------------------------------------------------------------------


def _assess_dimension(points, resolution, station_data, target_lat, target_lng,
                      obs_key="obs_count"):
    """Assess station coverage + historical data for one dimension.

    Returns a dict with ``station_coverage`` and ``historical_data`` sub-dicts,
    plus an overall ``level`` for the dimension.
    """
    if not station_data:
        return dict(_EMPTY_DIM), "poor"

    total_pts = len(points)

    # --- Historical data (coverage + depth) ---
    obs_counts = [p.get(obs_key, 0) for p in points]

    if total_pts > 0:
        coverage_val = round(
            sum(1 for o in obs_counts if o > 0) / total_pts * 100, 1
        )
        good_baseline = _GOOD_OBS.get(resolution, 500)
        per_point = [min(o / good_baseline, 1.0) for o in obs_counts]
        depth_val = round(sum(per_point) / total_pts * 100, 1)
    else:
        coverage_val = 0.0
        depth_val = 0.0

    coverage_level = _classify(coverage_val, _COVERAGE_GOOD, _COVERAGE_FAIR)
    depth_level = _classify(depth_val, _DEPTH_GOOD, _DEPTH_FAIR)
    hd_level = _FACTOR_LEVELS[
        min(_LEVEL_ORDER[coverage_level], _LEVEL_ORDER[depth_level])
    ]
    hd_val = round((coverage_val + depth_val) / 2, 1)

    # --- Station coverage (proximity + directional spread) ---
    avg_dist = sum(
        sd["station"]["distance_km"] * sd["weight"] for sd in station_data
    )
    prox_val = max(0.0, min(100.0, round(
        (1 - min(avg_dist, 200) / 200) * 100, 1
    )))
    prox_level = _classify(
        avg_dist, _PROX_GOOD_KM, _PROX_FAIR_KM, higher_is_better=False
    )

    bearings = [
        _bearing(
            target_lat, target_lng,
            sd["station"]["latitude"], sd["station"]["longitude"],
        )
        for sd in station_data
    ]
    spread = _angular_spread(bearings)
    dir_val = round(min(spread / 360, 1.0) * 100, 1)
    dir_level = _classify(spread, _DIR_GOOD_DEG, _DIR_FAIR_DEG)

    max_weight = max(sd["weight"] for sd in station_data)
    effective_dir = dir_level
    if max_weight >= 0.85:
        effective_dir = "good"
    elif max_weight >= 0.60:
        effective_dir = _FACTOR_LEVELS[min(_LEVEL_ORDER[dir_level] + 1, 2)]

    sc_level = _FACTOR_LEVELS[
        min(_LEVEL_ORDER[prox_level], _LEVEL_ORDER[effective_dir])
    ]
    if effective_dir == "good" and dir_level != "good":
        sc_val = prox_val
    else:
        sc_val = round((prox_val + dir_val) / 2, 1)

    # Summaries
    top_station = max(station_data, key=lambda sd: sd["weight"])
    top_name = top_station["station"]["name"]
    weights = [sd["weight"] for sd in station_data]

    station_summary = _build_station_summary(
        prox_level=prox_level, dir_level=dir_level,
        max_weight=max_weight, top_name=top_name,
        bearings=bearings, weights=weights,
    )
    data_summary = _build_data_summary(
        coverage_pct=coverage_val,
        coverage_level=coverage_level,
        depth_level=depth_level,
    )

    dim_level = _FACTOR_LEVELS[
        min(_LEVEL_ORDER[hd_level], _LEVEL_ORDER[sc_level])
    ]

    dim_result = {
        "station_coverage": {
            "value": sc_val,
            "level": sc_level,
            "summary": station_summary,
        },
        "historical_data": {
            "value": hd_val,
            "level": hd_level,
            "summary": data_summary,
        },
    }

    return dim_result, dim_level


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_quality(
    cloud_points: list[dict],
    lightning_points: list[dict],
    resolution: str,
    cloud_station_data: list[dict],
    lightning_station_data: list[dict],
    target_lat: float,
    target_lng: float,
) -> dict:
    """Compute a report-card data quality assessment with independent
    cloud and lightning dimensions.

    Each dimension gets its own station-coverage and historical-data grades.
    The overall level equals the worst factor across both dimensions.
    """
    cloud_dim, cloud_level = _assess_dimension(
        cloud_points, resolution, cloud_station_data,
        target_lat, target_lng, obs_key="obs_count",
    )

    if lightning_station_data:
        lightning_dim, lightning_level = _assess_dimension(
            lightning_points, resolution, lightning_station_data,
            target_lat, target_lng, obs_key="lightning_obs_count",
        )
    else:
        lightning_dim = dict(_EMPTY_DIM)
        lightning_dim["station_coverage"]["summary"] = (
            "No nearby stations record lightning observations."
        )
        lightning_dim["historical_data"]["summary"] = (
            "No lightning data is available for this area."
        )
        lightning_level = "poor"

    all_levels = [cloud_level]
    if lightning_station_data:
        all_levels.append(lightning_level)
    else:
        # No lightning stations caps overall at "medium"
        all_levels.append("fair")

    worst = min(_LEVEL_ORDER[lv] for lv in all_levels)
    overall = _LEVEL_MAP[worst]

    return {
        "level": overall,
        "cloud": cloud_dim,
        "lightning": lightning_dim,
    }
