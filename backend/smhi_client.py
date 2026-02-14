"""SMHI data access layer.

Handles all HTTP communication with the SMHI Open Data Metobs API,
CSV parsing, and file-based caching.  No business logic lives here.
"""

import csv
import json
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# SMHI API
# ---------------------------------------------------------------------------

SMHI_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0"

# Parameter IDs
PARAM_CLOUD_COVERAGE = 16   # Total molnmängd (%)
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

# ---------------------------------------------------------------------------
# File cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# SMHI corrected-archive updates roughly monthly; 7 days is a safe middle ground.
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _is_cache_fresh(path: Path) -> bool:
    """Return True if *path* exists and is younger than CACHE_MAX_AGE_SECONDS."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_SECONDS


def read_result_cache(station_id: str) -> dict | None:
    """Return cached aggregated result for *station_id*, or None if stale/missing."""
    result_cache = CACHE_DIR / "results"
    result_cache.mkdir(exist_ok=True)
    result_file = result_cache / f"station_{station_id}.json"
    if _is_cache_fresh(result_file):
        return json.loads(result_file.read_text(encoding="utf-8"))
    return None


def write_result_cache(station_id: str, data: dict) -> None:
    """Persist an aggregated result dict to the file cache."""
    result_cache = CACHE_DIR / "results"
    result_cache.mkdir(exist_ok=True)
    result_file = result_cache / f"station_{station_id}.json"
    result_file.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP + CSV parsing
# ---------------------------------------------------------------------------


def fetch_station_list(parameter_id: int) -> list[dict]:
    """Fetch all stations for a given SMHI parameter.

    Returns list of dicts: {key, name, latitude, longitude, active}
    """
    url = f"{SMHI_BASE}/parameter/{parameter_id}.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json().get("station", [])


def fetch_station_csv(parameter_id: int, station_id: str) -> str:
    """Download the corrected-archive CSV for a parameter/station pair.

    Results are cached to disk under ``cache/csv/`` so subsequent requests
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


def parse_smhi_csv(csv_text: str) -> list[dict]:
    """Parse SMHI semicolon-delimited CSV, skipping header blocks.

    Returns list of dicts with keys: date, time, value, quality.
    The CSV has several header lines before the actual data starts at a line
    matching ``Datum;Tid (UTC);...``.
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

    data_lines = lines[data_start:]
    reader = csv.reader(data_lines, delimiter=";")
    next(reader)  # skip header row

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
