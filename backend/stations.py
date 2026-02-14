"""Station discovery, listing, and adaptive selection.

Knows how to find SMHI stations, rank them by distance, and
adaptively select a subset using an IDW weight threshold.
"""

import math

from smhi_client import (
    PARAM_CLOUD_COVERAGE,
    PARAM_PRESENT_WEATHER,
    fetch_station_list,
)


# ---------------------------------------------------------------------------
# Geographic utilities
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in km between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Station queries
# ---------------------------------------------------------------------------


def get_nearby_stations(
    lat: float, lng: float,
    parameter_id: int = PARAM_CLOUD_COVERAGE,
    count: int = 10,
) -> list[dict]:
    """Return the *count* nearest active SMHI stations for *parameter_id*.

    Each station dict: ``{id, name, latitude, longitude, distance_km}``
    """
    raw_stations = fetch_station_list(parameter_id)

    stations = []
    for s in raw_stations:
        if not s.get("active"):
            continue
        dist = haversine_km(lat, lng, s["latitude"], s["longitude"])
        stations.append(
            {
                "id": s["key"],
                "name": s["name"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "distance_km": round(dist, 1),
            }
        )

    stations.sort(key=lambda s: s["distance_km"])
    return stations[:count]


def get_all_stations() -> list[dict]:
    """Return all active SMHI stations with info on which parameters they support.

    Merges stations from both the cloud coverage and present weather parameter
    lists so that weather-only stations (e.g. airports) also appear.

    Each station dict: ``{id, name, latitude, longitude, has_cloud_data, has_weather_data}``
    """
    cloud_raw = fetch_station_list(PARAM_CLOUD_COVERAGE)
    weather_raw = fetch_station_list(PARAM_PRESENT_WEATHER)

    cloud_ids = {s["key"] for s in cloud_raw if s.get("active")}
    weather_ids = {s["key"] for s in weather_raw if s.get("active")}

    # Build a merged dict keyed by station id
    merged: dict[str, dict] = {}

    for s in cloud_raw:
        if not s.get("active"):
            continue
        merged[s["key"]] = {
            "id": s["key"],
            "name": s["name"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
        }

    for s in weather_raw:
        if not s.get("active"):
            continue
        if s["key"] not in merged:
            merged[s["key"]] = {
                "id": s["key"],
                "name": s["name"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
            }

    stations = [
        {
            **info,
            "has_cloud_data": info["id"] in cloud_ids,
            "has_weather_data": info["id"] in weather_ids,
        }
        for info in merged.values()
    ]

    stations.sort(key=lambda s: s["name"])
    return stations


# ---------------------------------------------------------------------------
# Adaptive station selection
# ---------------------------------------------------------------------------

# Minimum number of stations always included, regardless of weight.
MIN_STATIONS = 2

# Stop adding stations when the next one would contribute less than this
# fraction of the cumulative weight.
WEIGHT_THRESHOLD = 0.02

# Clamp distances below this value (km) to avoid division by zero.
MIN_DIST_KM = 0.1


def select_stations(candidates: list[dict]) -> list[dict]:
    """Adaptively select stations from a distance-sorted candidate list.

    Uses inverse-distance weighting (power=2) and stops adding stations once
    the next candidate would contribute less than ``WEIGHT_THRESHOLD`` of the
    cumulative total.  At least ``MIN_STATIONS`` are always included.

    *candidates* must be sorted by ``distance_km`` (ascending).

    Returns a list of dicts, each containing the original station dict under
    the ``"station"`` key plus a ``"raw_weight"`` value.
    """
    selected: list[dict] = []
    for i, s in enumerate(candidates):
        dist = max(s["distance_km"], MIN_DIST_KM)
        raw_weight = 1.0 / (dist ** 2)

        if i >= MIN_STATIONS:
            total_so_far = sum(sd["raw_weight"] for sd in selected)
            if raw_weight / (total_so_far + raw_weight) < WEIGHT_THRESHOLD:
                break

        selected.append({"station": s, "raw_weight": raw_weight})

    return selected
