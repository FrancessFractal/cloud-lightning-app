"""Weather data aggregation and multi-station interpolation.

Contains the core business logic:
- Aggregating raw SMHI observations into summaries at day/month/year resolution.
- Blending multiple stations into a location estimate via IDW.
- Wilson score confidence intervals for lightning probability.
"""

import calendar
import math
from collections import defaultdict

import requests

from smhi_client import (
    LIGHTNING_CODES,
    MONTH_NAMES,
    PARAM_CLOUD_COVERAGE,
    PARAM_PRESENT_WEATHER,
    fetch_station_csv,
    parse_smhi_csv,
    read_result_cache,
    write_result_cache,
)
from stations import get_nearby_stations, select_stations

VALID_RESOLUTIONS = ("day", "month", "year")


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _wilson_interval(successes: int, total: int, z: float = 1.96):
    """95% Wilson score confidence interval for a binomial proportion.

    Returns (lower_pct, upper_pct) as percentages, or (None, None) if no data.
    """
    if total == 0:
        return None, None
    p = successes / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(
        p * (1 - p) / total + z**2 / (4 * total**2)
    )
    return (
        round(max(0, center - margin) * 100, 2),
        round(min(1, center + margin) * 100, 2),
    )


# ---------------------------------------------------------------------------
# Raw data fetching (shared by all resolutions)
# ---------------------------------------------------------------------------


def _fetch_raw_observations(station_id: str):
    """Fetch and parse cloud + weather CSVs for a station.

    Returns (cloud_rows, weather_rows, has_lightning_data).
    Each row is a dict with keys: date, time, value, quality.
    """
    cloud_rows = []
    try:
        cloud_csv = fetch_station_csv(PARAM_CLOUD_COVERAGE, station_id)
        cloud_rows = parse_smhi_csv(cloud_csv)
    except requests.HTTPError:
        pass

    weather_rows = []
    has_lightning_data = False
    try:
        weather_csv = fetch_station_csv(PARAM_PRESENT_WEATHER, station_id)
        weather_rows = parse_smhi_csv(weather_csv)
        has_lightning_data = len(weather_rows) > 0
    except requests.HTTPError:
        pass

    return cloud_rows, weather_rows, has_lightning_data


# ---------------------------------------------------------------------------
# Aggregation helpers per resolution
# ---------------------------------------------------------------------------


# Minimum observations required for a confidence interval to be meaningful.
# Below this threshold the Wilson interval can be absurdly wide (e.g. [0%-79%]
# from a single observation) and distorts the chart.
MIN_CI_OBSERVATIONS = 30


def _make_point(label, cloud_values, lightning_bucket, has_lightning_data):
    """Build a single data point dict with cloud avg, lightning stats, and CI."""
    cloud_avg = (
        round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None
    )

    lightning_pct = None
    lightning_lower = None
    lightning_upper = None
    if has_lightning_data and lightning_bucket and lightning_bucket["total"] > 0:
        total = lightning_bucket["total"]
        hits = lightning_bucket["lightning"]
        lightning_pct = round((hits / total) * 100, 2)
        if total >= MIN_CI_OBSERVATIONS:
            lightning_lower, lightning_upper = _wilson_interval(hits, total)

    return {
        "label": label,
        "cloud_coverage_avg": cloud_avg,
        "lightning_probability": lightning_pct,
        "lightning_lower": lightning_lower,
        "lightning_upper": lightning_upper,
        "obs_count": len(cloud_values),
    }


def _aggregate_monthly(cloud_rows, weather_rows, has_lightning_data):
    """Aggregate into 12 monthly points (all-time averages)."""
    cloud_by_month: dict[int, list[float]] = defaultdict(list)
    for row in cloud_rows:
        month = int(row["date"].split("-")[1])
        cloud_by_month[month].append(row["value"])

    lightning_by_month: dict[int, dict] = defaultdict(
        lambda: {"total": 0, "lightning": 0}
    )
    for row in weather_rows:
        month = int(row["date"].split("-")[1])
        lightning_by_month[month]["total"] += 1
        if int(row["value"]) in LIGHTNING_CODES:
            lightning_by_month[month]["lightning"] += 1

    return [
        _make_point(
            MONTH_NAMES[m - 1],
            cloud_by_month.get(m, []),
            lightning_by_month.get(m),
            has_lightning_data,
        )
        for m in range(1, 13)
    ]


def _aggregate_daily(cloud_rows, weather_rows, has_lightning_data):
    """Aggregate into 365/366 daily points (day-of-year averages across all years)."""
    cloud_by_day: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in cloud_rows:
        parts = row["date"].split("-")
        key = (int(parts[1]), int(parts[2]))
        cloud_by_day[key].append(row["value"])

    lightning_by_day: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"total": 0, "lightning": 0}
    )
    for row in weather_rows:
        parts = row["date"].split("-")
        key = (int(parts[1]), int(parts[2]))
        lightning_by_day[key]["total"] += 1
        if int(row["value"]) in LIGHTNING_CODES:
            lightning_by_day[key]["lightning"] += 1

    points = []
    for m in range(1, 13):
        days_in_month = calendar.monthrange(2000, m)[1]
        for d in range(1, days_in_month + 1):
            key = (m, d)
            points.append(
                _make_point(
                    f"{MONTH_NAMES[m - 1]} {d:02d}",
                    cloud_by_day.get(key, []),
                    lightning_by_day.get(key),
                    has_lightning_data,
                )
            )
    return points


def _aggregate_yearly(cloud_rows, weather_rows, has_lightning_data):
    """Aggregate into per-year points showing long-term trends."""
    cloud_by_year: dict[int, list[float]] = defaultdict(list)
    for row in cloud_rows:
        year = int(row["date"].split("-")[0])
        cloud_by_year[year].append(row["value"])

    lightning_by_year: dict[int, dict] = defaultdict(
        lambda: {"total": 0, "lightning": 0}
    )
    for row in weather_rows:
        year = int(row["date"].split("-")[0])
        lightning_by_year[year]["total"] += 1
        if int(row["value"]) in LIGHTNING_CODES:
            lightning_by_year[year]["lightning"] += 1

    all_years = sorted(set(cloud_by_year.keys()) | set(lightning_by_year.keys()))

    return [
        _make_point(
            str(year),
            cloud_by_year.get(year, []),
            lightning_by_year.get(year),
            has_lightning_data,
        )
        for year in all_years
    ]


# ---------------------------------------------------------------------------
# Single-station aggregation
# ---------------------------------------------------------------------------

_AGGREGATORS = {
    "day": _aggregate_daily,
    "month": _aggregate_monthly,
    "year": _aggregate_yearly,
}


def get_station_weather_data(station_id: str, resolution: str = "month") -> dict:
    """Fetch and aggregate cloud coverage and lightning data for one station.

    *resolution* controls the grouping: ``"day"`` (365 points),
    ``"month"`` (12 points), or ``"year"`` (one per year).

    Results are cached per station+resolution.
    """
    if resolution not in VALID_RESOLUTIONS:
        resolution = "month"

    cached = read_result_cache(station_id, resolution)
    if cached is not None:
        return cached

    cloud_rows, weather_rows, has_lightning_data = _fetch_raw_observations(station_id)

    aggregator = _AGGREGATORS[resolution]
    points = aggregator(cloud_rows, weather_rows, has_lightning_data)

    result = {
        "station_id": station_id,
        "resolution": resolution,
        "has_lightning_data": has_lightning_data,
        "points": points,
    }

    write_result_cache(station_id, resolution, result)
    return result


# Keep backward-compatible alias
def get_monthly_weather_data(station_id: str) -> dict:
    """Backward-compatible wrapper -- returns monthly resolution."""
    return get_station_weather_data(station_id, resolution="month")


# ---------------------------------------------------------------------------
# Multi-station interpolation
# ---------------------------------------------------------------------------


def get_location_weather(lat: float, lng: float, resolution: str = "month") -> dict:
    """Estimate weather patterns at an exact location.

    1. Fetches a pool of nearby station candidates.
    2. Adaptively selects which stations to use.
    3. Fetches data for each selected station at the given *resolution*.
    4. Blends values using inverse distance weighting.
    """
    if resolution not in VALID_RESOLUTIONS:
        resolution = "month"

    nearby = get_nearby_stations(lat, lng, count=10)

    empty_quality = {
        "level": "low",
        "coverage": {"value": 0, "level": "poor"},
        "depth": {"value": 0, "level": "poor"},
        "proximity": {"value": 0, "level": "poor", "avg_km": None},
        "direction": {"value": 0, "level": "poor", "spread_deg": 0},
        "median_obs": 0,
    }

    if not nearby:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "stations": [],
            "quality": empty_quality,
        }

    selected = select_stations(nearby)

    # Fetch per-station data
    station_data = []
    for sd in selected:
        try:
            data = get_station_weather_data(sd["station"]["id"], resolution)
            station_data.append({**sd, "data": data})
        except Exception:
            pass

    if not station_data:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "stations": [],
            "quality": empty_quality,
        }

    # Normalize weights
    total_weight = sum(sd["raw_weight"] for sd in station_data)
    for sd in station_data:
        sd["weight"] = sd["raw_weight"] / total_weight

    has_lightning = any(sd["data"].get("has_lightning_data") for sd in station_data)

    if resolution == "year":
        points = _blend_yearly(station_data, has_lightning)
    else:
        points = _blend_fixed(station_data, has_lightning)

    quality = _compute_quality(points, resolution, station_data, lat, lng)

    stations_info = [
        {
            "id": sd["station"]["id"],
            "name": sd["station"]["name"],
            "latitude": sd["station"]["latitude"],
            "longitude": sd["station"]["longitude"],
            "distance_km": sd["station"]["distance_km"],
            "weight_pct": round(sd["weight"] * 100, 1),
        }
        for sd in station_data
    ]

    return {
        "has_lightning_data": has_lightning,
        "resolution": resolution,
        "points": points,
        "stations": stations_info,
        "quality": quality,
    }


# ---------------------------------------------------------------------------
# Data quality assessment  (report-card model)
# ---------------------------------------------------------------------------

# Expected observations per data point for "well-covered" data.
_GOOD_OBS = {
    "day": 30,
    "month": 500,
    "year": 2000,
}

# Thresholds for each factor → good / fair / poor
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


def _compute_quality(points, resolution, station_data, target_lat, target_lng):
    """Compute a report-card data quality assessment.

    Each of four factors gets an independent level (good / fair / poor).
    The overall level equals the worst individual factor.

    Returns a dict with per-factor breakdowns and an overall level.
    """
    empty = {
        "level": "low",
        "coverage": {"value": 0, "level": "poor"},
        "depth": {"value": 0, "level": "poor"},
        "proximity": {"value": 0, "level": "poor", "avg_km": None},
        "direction": {"value": 0, "level": "poor", "spread_deg": 0},
        "median_obs": 0,
    }

    total_pts = len(points)
    if total_pts == 0:
        return empty

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
    prox_level = _classify(avg_dist, _PROX_GOOD_KM, _PROX_FAIR_KM,
                           higher_is_better=False)

    # --- 4. Directional coverage: angular spread of stations ---
    bearings = [
        _bearing(target_lat, target_lng,
                 sd["station"]["latitude"], sd["station"]["longitude"])
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


def _blend_point(label, station_entries, has_lightning):
    """Blend a single data point across weighted station entries.

    Each entry is (weight, point_dict).
    """
    cloud_sum = 0.0
    cloud_w = 0.0
    lightning_sum = 0.0
    lightning_w = 0.0
    lower_sum = 0.0
    lower_w = 0.0
    upper_sum = 0.0
    upper_w = 0.0
    obs_total = 0

    for w, pt in station_entries:
        obs_total += pt.get("obs_count", 0)

        if pt["cloud_coverage_avg"] is not None:
            cloud_sum += pt["cloud_coverage_avg"] * w
            cloud_w += w
        if pt["lightning_probability"] is not None:
            lightning_sum += pt["lightning_probability"] * w
            lightning_w += w
        if pt.get("lightning_lower") is not None:
            lower_sum += pt["lightning_lower"] * w
            lower_w += w
        if pt.get("lightning_upper") is not None:
            upper_sum += pt["lightning_upper"] * w
            upper_w += w

    return {
        "label": label,
        "cloud_coverage_avg": round(cloud_sum / cloud_w, 1) if cloud_w > 0 else None,
        "lightning_probability": round(lightning_sum / lightning_w, 2) if lightning_w > 0 else None,
        "lightning_lower": round(lower_sum / lower_w, 2) if lower_w > 0 else None,
        "lightning_upper": round(upper_sum / upper_w, 2) if upper_w > 0 else None,
        "obs_count": obs_total,
    }


def _blend_fixed(station_data, has_lightning):
    """Blend stations with a fixed number of points (day or month)."""
    num_points = len(station_data[0]["data"]["points"])
    points = []
    for idx in range(num_points):
        label = station_data[0]["data"]["points"][idx]["label"]
        entries = [
            (sd["weight"], sd["data"]["points"][idx]) for sd in station_data
        ]
        points.append(_blend_point(label, entries, has_lightning))
    return points


def _blend_yearly(station_data, has_lightning):
    """Blend stations for yearly resolution (variable-length point arrays)."""
    all_labels = {}
    for sd in station_data:
        for pt in sd["data"]["points"]:
            all_labels[pt["label"]] = True

    station_lookups = []
    for sd in station_data:
        lookup = {pt["label"]: pt for pt in sd["data"]["points"]}
        station_lookups.append((sd["weight"], lookup))

    points = []
    for label in sorted(all_labels.keys()):
        entries = []
        for w, lookup in station_lookups:
            pt = lookup.get(label)
            if pt is not None:
                entries.append((w, pt))
        points.append(_blend_point(label, entries, has_lightning))
    return points
