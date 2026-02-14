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
import math
from collections import defaultdict

import requests

SMHI_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

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
    """Download the corrected-archive CSV for a parameter/station pair."""
    url = (
        f"{SMHI_BASE}/parameter/{parameter_id}"
        f"/station/{station_id}/period/corrected-archive/data.csv"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def get_monthly_weather_data(station_id: str) -> dict:
    """Fetch and aggregate cloud coverage and lightning data for a station.

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
    lightning_by_month: dict[int, dict] = defaultdict(
        lambda: {"total": 0, "lightning": 0}
    )
    try:
        weather_csv = _fetch_station_csv(PARAM_PRESENT_WEATHER, station_id)
        weather_rows = _parse_smhi_csv(weather_csv)
        for row in weather_rows:
            month = int(row["date"].split("-")[1])
            lightning_by_month[month]["total"] += 1
            if int(row["value"]) in LIGHTNING_CODES:
                lightning_by_month[month]["lightning"] += 1
    except requests.HTTPError:
        pass  # station may not have weather data

    # --- Build monthly summary ---
    months = []
    for m in range(1, 13):
        cloud_values = cloud_by_month.get(m, [])
        cloud_avg = round(sum(cloud_values) / len(cloud_values), 1) if cloud_values else None

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

    return {"station_id": station_id, "months": months}
