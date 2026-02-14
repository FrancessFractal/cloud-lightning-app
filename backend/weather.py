"""Weather data aggregation and multi-station interpolation.

Contains the core business logic:
- Aggregating raw SMHI observations into summaries at day/month/year resolution.
- Blending multiple stations into a location estimate via IDW.
- Wilson score confidence intervals for lightning probability.

Data quality assessment lives in ``quality.py``.
"""

import calendar
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from smhi_client import (
    LIGHTNING_CODES,
    MONTH_NAMES,
    PARAM_CLOUD_COVERAGE,
    PARAM_PRESENT_WEATHER,
    fetch_and_parse_csv,
    read_result_cache,
    write_result_cache,
)
from quality import EMPTY_QUALITY, compute_quality
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

    Uses ``fetch_and_parse_csv`` which keeps parsed rows in memory so
    resolution switches don't re-read/re-parse the same files.

    Returns (cloud_rows, weather_rows, has_lightning_data).
    Each row is a dict with keys: date, time, value, quality.
    """
    cloud_rows = []
    try:
        cloud_rows = fetch_and_parse_csv(PARAM_CLOUD_COVERAGE, station_id)
    except requests.HTTPError:
        pass

    weather_rows = []
    has_lightning_data = False
    try:
        weather_rows = fetch_and_parse_csv(PARAM_PRESENT_WEATHER, station_id)
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


def _prefetch_csvs(station_ids: list[str]) -> None:
    """Download and parse CSVs for multiple stations in parallel.

    This warms both the on-disk CSV cache and the in-memory parsed-row
    cache so that subsequent ``get_station_weather_data`` calls are instant.
    Only stations whose CSVs are not already cached will trigger network I/O.
    """
    tasks = []
    for sid in station_ids:
        tasks.append((PARAM_CLOUD_COVERAGE, sid))
        tasks.append((PARAM_PRESENT_WEATHER, sid))

    def _fetch(param_id, sid):
        try:
            fetch_and_parse_csv(param_id, sid)
        except Exception:
            pass  # individual station failures are handled later

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_fetch, p, s) for p, s in tasks]
        for f in as_completed(futures):
            f.result()  # propagate unexpected exceptions


def get_location_weather(lat: float, lng: float, resolution: str = "month") -> dict:
    """Estimate weather patterns at an exact location.

    1. Fetches a pool of nearby station candidates.
    2. Adaptively selects which stations to use.
    3. Downloads CSVs for all stations in parallel (if not cached).
    4. Aggregates each station at the given *resolution*.
    5. Blends values using inverse distance weighting.
    """
    if resolution not in VALID_RESOLUTIONS:
        resolution = "month"

    nearby = get_nearby_stations(lat, lng, count=10)

    if not nearby:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "stations": [],
            "quality": dict(EMPTY_QUALITY),
        }

    selected = select_stations(nearby)

    # --- Parallel CSV pre-fetch (only for cache misses) -----------------------
    # Check which stations actually need CSV data (no result cache hit).
    # For stations that are already fully cached, skip the expensive CSV
    # read+parse entirely.
    uncached_ids = [
        sd["station"]["id"]
        for sd in selected
        if read_result_cache(sd["station"]["id"], resolution) is None
    ]
    if uncached_ids:
        _prefetch_csvs(uncached_ids)

    # Fetch per-station data (hits result cache for pre-computed stations)
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
            "quality": dict(EMPTY_QUALITY),
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

    # Quality is always assessed against yearly data so it stays stable
    # regardless of which resolution the user is viewing.  Yearly is the
    # right baseline because each year stands on its own — gaps in the
    # historical record (e.g. no data for 2006-2007) show up as missing
    # points, whereas monthly/daily averages across years hide them.
    if resolution == "year":
        quality_points = points
    else:
        yearly_data = []
        for sd in station_data:
            ydata = get_station_weather_data(sd["station"]["id"], "year")
            yearly_data.append({**sd, "data": ydata})
        quality_points = _blend_yearly(yearly_data, has_lightning)

    quality = compute_quality(quality_points, "year", station_data, lat, lng)

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
