"""Weather data aggregation and multi-station interpolation.

Contains the core business logic:
- Aggregating raw SMHI observations into summaries at day/month/year resolution.
- Blending multiple stations into a location estimate via IDW.
"""

import calendar
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

    points = []
    for m in range(1, 13):
        cloud_values = cloud_by_month.get(m, [])
        cloud_avg = (
            round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None
        )
        lightning_pct = _lightning_pct(lightning_by_month.get(m), has_lightning_data)
        points.append(
            {
                "label": MONTH_NAMES[m - 1],
                "cloud_coverage_avg": cloud_avg,
                "lightning_probability": lightning_pct,
                "obs_count": len(cloud_values),
            }
        )
    return points


def _aggregate_daily(cloud_rows, weather_rows, has_lightning_data):
    """Aggregate into 365/366 daily points (day-of-year averages across all years)."""
    cloud_by_day: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in cloud_rows:
        parts = row["date"].split("-")
        key = (int(parts[1]), int(parts[2]))  # (month, day)
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
        days_in_month = calendar.monthrange(2000, m)[1]  # use leap year for max days
        for d in range(1, days_in_month + 1):
            key = (m, d)
            cloud_values = cloud_by_day.get(key, [])
            cloud_avg = (
                round(sum(cloud_values) / len(cloud_values), 1)
                if cloud_values
                else None
            )
            lightning_pct = _lightning_pct(
                lightning_by_day.get(key), has_lightning_data
            )
            points.append(
                {
                    "label": f"{MONTH_NAMES[m - 1]} {d:02d}",
                    "cloud_coverage_avg": cloud_avg,
                    "lightning_probability": lightning_pct,
                    "obs_count": len(cloud_values),
                }
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

    points = []
    for year in all_years:
        cloud_values = cloud_by_year.get(year, [])
        cloud_avg = (
            round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None
        )
        lightning_pct = _lightning_pct(
            lightning_by_year.get(year), has_lightning_data
        )
        points.append(
            {
                "label": str(year),
                "cloud_coverage_avg": cloud_avg,
                "lightning_probability": lightning_pct,
                "obs_count": len(cloud_values),
            }
        )
    return points


def _lightning_pct(bucket, has_lightning_data):
    """Compute lightning probability % from a {total, lightning} bucket."""
    if not has_lightning_data:
        return None
    if bucket is None or bucket["total"] == 0:
        return None
    return round((bucket["lightning"] / bucket["total"]) * 100, 2)


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

    if not nearby:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "stations": [],
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
        }

    # Normalize weights
    total_weight = sum(sd["raw_weight"] for sd in station_data)
    for sd in station_data:
        sd["weight"] = sd["raw_weight"] / total_weight

    has_lightning = any(sd["data"].get("has_lightning_data") for sd in station_data)

    # Determine point count from the first station (all stations at same
    # resolution produce the same number of points for day/month; for year
    # they may differ, so we use the union of labels).
    if resolution == "year":
        points = _blend_yearly(station_data, has_lightning)
    else:
        points = _blend_fixed(station_data, has_lightning)

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
    }


def _blend_fixed(station_data, has_lightning):
    """Blend stations with a fixed number of points (day or month)."""
    num_points = len(station_data[0]["data"]["points"])
    points = []
    for idx in range(num_points):
        label = station_data[0]["data"]["points"][idx]["label"]
        cloud_sum = 0.0
        cloud_w = 0.0
        lightning_sum = 0.0
        lightning_w = 0.0
        obs_total = 0

        for sd in station_data:
            w = sd["weight"]
            pt = sd["data"]["points"][idx]
            obs_total += pt.get("obs_count", 0)

            if pt["cloud_coverage_avg"] is not None:
                cloud_sum += pt["cloud_coverage_avg"] * w
                cloud_w += w
            if pt["lightning_probability"] is not None:
                lightning_sum += pt["lightning_probability"] * w
                lightning_w += w

        points.append(
            {
                "label": label,
                "cloud_coverage_avg": round(cloud_sum / cloud_w, 1) if cloud_w > 0 else None,
                "lightning_probability": round(lightning_sum / lightning_w, 2) if lightning_w > 0 else None,
                "obs_count": obs_total,
            }
        )
    return points


def _blend_yearly(station_data, has_lightning):
    """Blend stations for yearly resolution (variable-length point arrays)."""
    # Collect the union of all year labels
    all_labels = {}
    for sd in station_data:
        for pt in sd["data"]["points"]:
            all_labels[pt["label"]] = True

    # Build a lookup per station: label -> point
    station_lookups = []
    for sd in station_data:
        lookup = {pt["label"]: pt for pt in sd["data"]["points"]}
        station_lookups.append((sd["weight"], lookup))

    points = []
    for label in sorted(all_labels.keys()):
        cloud_sum = 0.0
        cloud_w = 0.0
        lightning_sum = 0.0
        lightning_w = 0.0
        obs_total = 0

        for w, lookup in station_lookups:
            pt = lookup.get(label)
            if pt is None:
                continue
            obs_total += pt.get("obs_count", 0)
            if pt["cloud_coverage_avg"] is not None:
                cloud_sum += pt["cloud_coverage_avg"] * w
                cloud_w += w
            if pt["lightning_probability"] is not None:
                lightning_sum += pt["lightning_probability"] * w
                lightning_w += w

        points.append(
            {
                "label": label,
                "cloud_coverage_avg": round(cloud_sum / cloud_w, 1) if cloud_w > 0 else None,
                "lightning_probability": round(lightning_sum / lightning_w, 2) if lightning_w > 0 else None,
                "obs_count": obs_total,
            }
        )
    return points
