"""Shared fixtures and helpers for backend tests.

All tests run against synthetic data — no network calls or disk caching.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Synthetic station data
# ---------------------------------------------------------------------------

# A set of fake stations with known positions around Stockholm (59.33, 18.07)
FAKE_CLOUD_STATIONS = [
    {"key": "C1", "name": "Close-Cloud",   "latitude": 59.35, "longitude": 18.10, "active": True},
    {"key": "C2", "name": "Mid-Cloud",     "latitude": 59.60, "longitude": 18.30, "active": True},
    {"key": "C3", "name": "Far-Cloud",     "latitude": 60.50, "longitude": 18.50, "active": True},
    {"key": "C4", "name": "Inactive-Cloud", "latitude": 59.33, "longitude": 18.07, "active": False},
]

FAKE_WEATHER_STATIONS = [
    {"key": "W1", "name": "Close-Weather", "latitude": 59.34, "longitude": 18.08, "active": True},
    {"key": "C1", "name": "Close-Cloud",   "latitude": 59.35, "longitude": 18.10, "active": True},  # overlap
    {"key": "W2", "name": "Mid-Weather",   "latitude": 59.55, "longitude": 18.25, "active": True},
    {"key": "W3", "name": "Decommissioned","latitude": 59.33, "longitude": 18.06, "active": False},
]


def fake_fetch_station_list(param_id):
    """Return synthetic station list for a given parameter."""
    from smhi_client import PARAM_CLOUD_COVERAGE, PARAM_PRESENT_WEATHER
    if param_id == PARAM_CLOUD_COVERAGE:
        return FAKE_CLOUD_STATIONS
    elif param_id == PARAM_PRESENT_WEATHER:
        return FAKE_WEATHER_STATIONS
    return []


# ---------------------------------------------------------------------------
# Synthetic observation rows
# ---------------------------------------------------------------------------

def make_cloud_rows(months=range(1, 13), value=50.0, years=None):
    """Generate synthetic cloud observation rows."""
    if years is None:
        years = range(2010, 2021)
    rows = []
    for y in years:
        for m in months:
            for d in (1, 15):
                rows.append({
                    "date": f"{y}-{m:02d}-{d:02d}",
                    "time": "12:00:00",
                    "value": value,
                    "quality": "G",
                })
    return rows


def make_weather_rows(months=range(1, 13), lightning_code=None, years=None):
    """Generate synthetic present-weather rows.

    If *lightning_code* is given, every row gets that WMO code.
    Otherwise rows get code 0 (no significant weather).
    """
    if years is None:
        years = range(2010, 2021)
    code = lightning_code if lightning_code is not None else 0
    rows = []
    for y in years:
        for m in months:
            for d in (1, 15):
                rows.append({
                    "date": f"{y}-{m:02d}-{d:02d}",
                    "time": "12:00:00",
                    "value": code,
                    "quality": "G",
                })
    return rows
