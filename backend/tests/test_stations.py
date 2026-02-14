"""Tests for station discovery and selection logic."""

from unittest.mock import patch

from tests.conftest import fake_fetch_station_list


# ---------------------------------------------------------------------------
# get_nearby_stations
# ---------------------------------------------------------------------------

@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_nearby_stations_returns_only_active(mock_list):
    """Inactive stations must be excluded from the result."""
    from stations import get_nearby_stations
    from smhi_client import PARAM_CLOUD_COVERAGE

    result = get_nearby_stations(59.33, 18.07, parameter_id=PARAM_CLOUD_COVERAGE)
    ids = {s["id"] for s in result}
    assert "C4" not in ids, "Inactive station C4 should be excluded"


@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_nearby_stations_respects_parameter_id(mock_list):
    """Cloud and weather queries must return different station pools."""
    from stations import get_nearby_stations
    from smhi_client import PARAM_CLOUD_COVERAGE, PARAM_PRESENT_WEATHER

    cloud = get_nearby_stations(59.33, 18.07, parameter_id=PARAM_CLOUD_COVERAGE)
    weather = get_nearby_stations(59.33, 18.07, parameter_id=PARAM_PRESENT_WEATHER)

    cloud_ids = {s["id"] for s in cloud}
    weather_ids = {s["id"] for s in weather}

    # W1 is weather-only; it must NOT appear in cloud results
    assert "W1" not in cloud_ids, "Weather-only station W1 leaked into cloud list"
    # W1 must appear in weather results
    assert "W1" in weather_ids, "Weather station W1 missing from weather list"


@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_nearby_stations_decommissioned_excluded(mock_list):
    """Decommissioned weather stations must not appear in results."""
    from stations import get_nearby_stations
    from smhi_client import PARAM_PRESENT_WEATHER

    result = get_nearby_stations(59.33, 18.07, parameter_id=PARAM_PRESENT_WEATHER)
    ids = {s["id"] for s in result}
    assert "W3" not in ids, "Decommissioned station W3 should be excluded"


@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_nearby_stations_sorted_by_distance(mock_list):
    """Results must be sorted nearest-first."""
    from stations import get_nearby_stations
    from smhi_client import PARAM_CLOUD_COVERAGE

    result = get_nearby_stations(59.33, 18.07, parameter_id=PARAM_CLOUD_COVERAGE)
    distances = [s["distance_km"] for s in result]
    assert distances == sorted(distances), "Stations should be sorted by distance"


# ---------------------------------------------------------------------------
# select_stations (adaptive IDW selection)
# ---------------------------------------------------------------------------

def test_select_stations_minimum_two():
    """At least MIN_STATIONS (2) must be selected even if second is far away."""
    from stations import select_stations

    candidates = [
        {"id": "A", "name": "Near", "latitude": 59.33, "longitude": 18.07, "distance_km": 1.0},
        {"id": "B", "name": "Far",  "latitude": 60.00, "longitude": 19.00, "distance_km": 500.0},
    ]
    selected = select_stations(candidates)
    assert len(selected) >= 2, "Must always select at least MIN_STATIONS"


def test_select_stations_stops_at_threshold():
    """Distant stations below the weight threshold must be dropped."""
    from stations import select_stations

    candidates = [
        {"id": "A", "name": "Near",    "latitude": 59.33, "longitude": 18.07, "distance_km": 1.0},
        {"id": "B", "name": "Medium",  "latitude": 59.40, "longitude": 18.10, "distance_km": 10.0},
        {"id": "C", "name": "VeryFar", "latitude": 65.00, "longitude": 20.00, "distance_km": 1000.0},
    ]
    selected = select_stations(candidates)
    selected_ids = {s["station"]["id"] for s in selected}

    # Station at 1000 km has weight 1e-6, vs station at 1 km with weight 1.0
    # That's way below WEIGHT_THRESHOLD (0.02), so C should be dropped
    assert "C" not in selected_ids, "Very distant station should be below weight threshold"


def test_select_stations_zero_distance_clamped():
    """A station at distance 0 should be clamped to MIN_DIST_KM, not crash."""
    from stations import select_stations

    candidates = [
        {"id": "A", "name": "Here", "latitude": 59.33, "longitude": 18.07, "distance_km": 0.0},
        {"id": "B", "name": "Near", "latitude": 59.34, "longitude": 18.08, "distance_km": 2.0},
    ]
    selected = select_stations(candidates)
    assert len(selected) >= 1
    assert selected[0]["raw_weight"] > 0


# ---------------------------------------------------------------------------
# get_all_stations (merged listing)
# ---------------------------------------------------------------------------

@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_all_stations_includes_weather_only(mock_list):
    """Stations that only record weather (not cloud) must appear in the listing."""
    from stations import get_all_stations

    result = get_all_stations()
    ids = {s["id"] for s in result}

    # W1 is a weather-only station — it must appear
    assert "W1" in ids, "Weather-only station W1 must appear in all-stations"
    # And its flags should be correct
    w1 = next(s for s in result if s["id"] == "W1")
    assert w1["has_cloud_data"] is False
    assert w1["has_weather_data"] is True


@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_all_stations_overlap_correct_flags(mock_list):
    """A station in both lists must have both flags set to True."""
    from stations import get_all_stations

    result = get_all_stations()
    c1 = next(s for s in result if s["id"] == "C1")
    assert c1["has_cloud_data"] is True
    assert c1["has_weather_data"] is True


@patch("stations.fetch_station_list", side_effect=fake_fetch_station_list)
def test_all_stations_excludes_inactive(mock_list):
    """Inactive stations from either list must be excluded."""
    from stations import get_all_stations

    result = get_all_stations()
    ids = {s["id"] for s in result}
    assert "C4" not in ids, "Inactive cloud station should be excluded"
    assert "W3" not in ids, "Inactive weather station should be excluded"
