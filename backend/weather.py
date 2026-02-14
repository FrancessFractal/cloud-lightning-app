"""Weather data aggregation and multi-station interpolation.

Contains the core business logic:
- Aggregating raw SMHI observations into monthly summaries (single station).
- Blending multiple stations into a location estimate via IDW.
"""

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


# ---------------------------------------------------------------------------
# Single-station aggregation
# ---------------------------------------------------------------------------


def get_monthly_weather_data(station_id: str) -> dict:
    """Fetch and aggregate cloud coverage and lightning data for one station.

    Results are cached to disk as JSON so the expensive CSV parsing
    only happens once per station (until the cache expires).

    Returns::

        {
            "station_id": "...",
            "has_lightning_data": True/False,
            "months": [
                {"month": "Jan", "cloud_coverage_avg": 72.3, "lightning_probability": 0.4},
                ...  (12 entries, Jan-Dec)
            ]
        }
    """
    # Check result cache first
    cached = read_result_cache(station_id)
    if cached is not None:
        return cached

    # --- Cloud coverage (parameter 16) ---
    cloud_by_month: dict[int, list[float]] = defaultdict(list)
    try:
        cloud_csv = fetch_station_csv(PARAM_CLOUD_COVERAGE, station_id)
        cloud_rows = parse_smhi_csv(cloud_csv)
        for row in cloud_rows:
            month = int(row["date"].split("-")[1])
            cloud_by_month[month].append(row["value"])
    except requests.HTTPError:
        pass  # station may not have cloud data

    # --- Present weather / lightning (parameter 13) ---
    has_lightning_data = False
    lightning_by_month: dict[int, dict] = defaultdict(
        lambda: {"total": 0, "lightning": 0}
    )
    try:
        weather_csv = fetch_station_csv(PARAM_PRESENT_WEATHER, station_id)
        weather_rows = parse_smhi_csv(weather_csv)
        has_lightning_data = len(weather_rows) > 0
        for row in weather_rows:
            month = int(row["date"].split("-")[1])
            lightning_by_month[month]["total"] += 1
            if int(row["value"]) in LIGHTNING_CODES:
                lightning_by_month[month]["lightning"] += 1
    except requests.HTTPError:
        pass  # station does not have present weather data

    # --- Build monthly summary ---
    months = []
    for m in range(1, 13):
        cloud_values = cloud_by_month.get(m, [])
        cloud_avg = (
            round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None
        )

        if not has_lightning_data:
            lightning_pct = None
        else:
            ldata = lightning_by_month[m]
            lightning_pct = (
                round((ldata["lightning"] / ldata["total"]) * 100, 2)
                if ldata["total"] > 0
                else None
            )

        months.append(
            {
                "month": MONTH_NAMES[m - 1],
                "cloud_coverage_avg": cloud_avg,
                "lightning_probability": lightning_pct,
            }
        )

    result = {
        "station_id": station_id,
        "has_lightning_data": has_lightning_data,
        "months": months,
    }

    write_result_cache(station_id, result)
    return result


# ---------------------------------------------------------------------------
# Multi-station interpolation
# ---------------------------------------------------------------------------


def get_location_weather(lat: float, lng: float) -> dict:
    """Estimate weather patterns at an exact location.

    1. Fetches a pool of nearby station candidates.
    2. Adaptively selects which stations to use (via ``stations.select_stations``).
    3. Fetches monthly data for each selected station.
    4. Blends values using inverse distance weighting.

    Returns::

        {
            "has_lightning_data": True/False,
            "months": [{"month": "Jan", "cloud_coverage_avg": ..., "lightning_probability": ...}, ...],
            "stations": [{"id": "...", "name": "...", "distance_km": ..., "weight_pct": ...}, ...]
        }
    """
    nearby = get_nearby_stations(lat, lng, count=10)

    if not nearby:
        return {"has_lightning_data": False, "months": [], "stations": []}

    # Adaptive station selection
    selected = select_stations(nearby)

    # Fetch per-station data
    station_data = []
    for sd in selected:
        try:
            data = get_monthly_weather_data(sd["station"]["id"])
            station_data.append({**sd, "data": data})
        except Exception:
            pass  # skip stations that fail

    if not station_data:
        return {"has_lightning_data": False, "months": [], "stations": []}

    # Normalize weights
    total_weight = sum(sd["raw_weight"] for sd in station_data)
    for sd in station_data:
        sd["weight"] = sd["raw_weight"] / total_weight

    # Blend monthly values
    has_lightning = any(sd["data"].get("has_lightning_data") for sd in station_data)

    months = []
    for m_idx in range(12):
        cloud_sum = 0.0
        cloud_weight_sum = 0.0
        lightning_sum = 0.0
        lightning_weight_sum = 0.0

        for sd in station_data:
            w = sd["weight"]
            month_data = sd["data"]["months"][m_idx]

            if month_data["cloud_coverage_avg"] is not None:
                cloud_sum += month_data["cloud_coverage_avg"] * w
                cloud_weight_sum += w

            if month_data["lightning_probability"] is not None:
                lightning_sum += month_data["lightning_probability"] * w
                lightning_weight_sum += w

        cloud_avg = (
            round(cloud_sum / cloud_weight_sum, 1) if cloud_weight_sum > 0 else None
        )
        lightning_pct = (
            round(lightning_sum / lightning_weight_sum, 2)
            if lightning_weight_sum > 0
            else None
        )

        months.append(
            {
                "month": MONTH_NAMES[m_idx],
                "cloud_coverage_avg": cloud_avg,
                "lightning_probability": lightning_pct,
            }
        )

    stations_info = [
        {
            "id": sd["station"]["id"],
            "name": sd["station"]["name"],
            "distance_km": sd["station"]["distance_km"],
            "weight_pct": round(sd["weight"] * 100, 1),
        }
        for sd in station_data
    ]

    return {
        "has_lightning_data": has_lightning,
        "months": months,
        "stations": stations_info,
    }
