"""
Service module for interacting with the SMHI Open Data Metobs API.

Handles:
- Fetching station lists for specific parameters
- Parsing SMHI CSV data
- Calculating distances between coordinates (Haversine)
- Aggregating cloud coverage and lightning data by month
"""

import csv
import io
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import requests

SMHI_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Cache directory (sits next to this file)
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# How long cached files stay fresh (seconds).
# SMHI corrected-archive updates roughly monthly; 7 days is a safe middle ground.
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _is_cache_fresh(path: Path) -> bool:
    """Return True if a cached file exists and is younger than CACHE_MAX_AGE_SECONDS."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_SECONDS

# SMHI parameter IDs
PARAM_CLOUD_COVERAGE = 16  # Total molnmängd (%)
PARAM_PRESENT_WEATHER = 13  # Rådande väder (WMO codes)

# WMO present-weather codes that indicate lightning / thunder
LIGHTNING_CODES = {
    13,   # Kornblixt (heat lightning)
    17,   # Åska utan nederbörd (thunder without precipitation)
    29,   # Åska under senaste timmen (thunder last hour)
    91, 92, 93, 94, 95, 96, 97, 98, 99,  # Thunderstorm variants
    112,  # Blixt på avstånd (distant lightning)
    126,  # Åskväder (thunderstorm)
    190, 191, 192, 193, 194, 195, 196,  # Thunderstorm variants (extended)
    213,  # Blixt mellan moln och marken (cloud-to-ground lightning)
    217,  # Åska utan regnskur (thunder without rain shower)
    292, 293,  # Skurar eller åska (showers or thunder)
}

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def geocode_address(query: str) -> dict | None:
    """Geocode an address string using Nominatim (OpenStreetMap).

    Returns dict with lat, lng, display_name or None if not found.
    """
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "weather-app/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    hit = results[0]
    return {
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
        "display_name": hit["display_name"],
    }


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


def _get_active_station_ids(parameter_id: int) -> set[str]:
    """Return the set of active station IDs for a given parameter."""
    url = f"{SMHI_BASE}/parameter/{parameter_id}.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return {s["key"] for s in resp.json().get("station", []) if s.get("active")}


def get_nearby_stations(lat: float, lng: float, count: int = 5) -> list[dict]:
    """Return the *count* nearest active SMHI stations for cloud coverage.

    Each station dict: {id, name, latitude, longitude, distance_km}
    """
    url = f"{SMHI_BASE}/parameter/{PARAM_CLOUD_COVERAGE}.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    stations = []
    for s in data.get("station", []):
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

    Each station dict: {id, name, latitude, longitude, has_cloud_data, has_weather_data}
    """
    # Fetch station lists for both parameters in sequence
    cloud_ids = _get_active_station_ids(PARAM_CLOUD_COVERAGE)
    weather_ids = _get_active_station_ids(PARAM_PRESENT_WEATHER)

    # Build full station info from the cloud coverage parameter list (our primary)
    url = f"{SMHI_BASE}/parameter/{PARAM_CLOUD_COVERAGE}.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    stations = []
    for s in resp.json().get("station", []):
        if not s.get("active"):
            continue
        stations.append(
            {
                "id": s["key"],
                "name": s["name"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "has_cloud_data": s["key"] in cloud_ids,
                "has_weather_data": s["key"] in weather_ids,
            }
        )

    stations.sort(key=lambda s: s["name"])
    return stations


def _parse_smhi_csv(csv_text: str) -> list[dict]:
    """Parse SMHI semicolon-delimited CSV, skipping header blocks.

    Returns list of dicts with keys: date, time, value, quality.
    The CSV has several header lines before the actual data starts at a line
    matching 'Datum;Tid (UTC);...'.
    """
    lines = csv_text.splitlines()

    # Find the header row for the actual data
    data_start = None
    for i, line in enumerate(lines):
        if line.startswith("Datum;Tid"):
            data_start = i
            break

    if data_start is None:
        return []

    # Read from data_start onward
    data_lines = lines[data_start:]
    reader = csv.reader(data_lines, delimiter=";")
    header = next(reader)  # e.g. ['Datum', 'Tid (UTC)', 'Total molnmängd', 'Kvalitet', '', 'Tidsutsnitt:']

    rows = []
    for row in reader:
        if len(row) < 4:
            continue
        date_str = row[0].strip()
        time_str = row[1].strip()
        value_str = row[2].strip()
        quality = row[3].strip()

        if not date_str or not value_str:
            continue

        try:
            value = float(value_str)
        except ValueError:
            continue

        rows.append(
            {
                "date": date_str,
                "time": time_str,
                "value": value,
                "quality": quality,
            }
        )

    return rows


def _fetch_station_csv(parameter_id: int, station_id: str) -> str:
    """Download the corrected-archive CSV for a parameter/station pair.

    Results are cached to disk under cache/csv/ so subsequent requests
    for the same station+parameter are served instantly.
    """
    csv_cache = CACHE_DIR / "csv"
    csv_cache.mkdir(exist_ok=True)
    cache_file = csv_cache / f"param{parameter_id}_station{station_id}.csv"

    if _is_cache_fresh(cache_file):
        return cache_file.read_text(encoding="utf-8")

    url = (
        f"{SMHI_BASE}/parameter/{parameter_id}"
        f"/station/{station_id}/period/corrected-archive/data.csv"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    cache_file.write_text(resp.text, encoding="utf-8")
    return resp.text


def get_monthly_weather_data(station_id: str) -> dict:
    """Fetch and aggregate cloud coverage and lightning data for a station.

    Results are cached to disk as JSON so the expensive CSV parsing
    only happens once per station.

    Returns:
        {
            "station_id": "...",
            "months": [
                {
                    "month": "Jan",
                    "cloud_coverage_avg": 72.3,
                    "lightning_probability": 0.4,
                },
                ...  (12 entries, Jan-Dec)
            ]
        }
    """
    # Check result cache first
    result_cache = CACHE_DIR / "results"
    result_cache.mkdir(exist_ok=True)
    result_file = result_cache / f"station_{station_id}.json"

    if _is_cache_fresh(result_file):
        return json.loads(result_file.read_text(encoding="utf-8"))

    # --- Cloud coverage (parameter 16) ---
    cloud_by_month: dict[int, list[float]] = defaultdict(list)
    try:
        cloud_csv = _fetch_station_csv(PARAM_CLOUD_COVERAGE, station_id)
        cloud_rows = _parse_smhi_csv(cloud_csv)
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
        weather_csv = _fetch_station_csv(PARAM_PRESENT_WEATHER, station_id)
        weather_rows = _parse_smhi_csv(weather_csv)
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
        cloud_avg = round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None

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

    # Persist to cache
    result_file.write_text(json.dumps(result), encoding="utf-8")

    return result
