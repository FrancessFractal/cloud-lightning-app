"""Tests for the data quality assessment module.

Covers:
  - Independent quality for cloud and lightning dimensions
  - Overall level is worst of all factors
  - Missing lightning stations caps quality
  - Station proximity and directional spread grading
  - Dominant station overrides directional coverage
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_station_data(stations_with_weight):
    """Build station_data list from [(id, name, lat, lng, dist, weight), ...]"""
    return [
        {
            "station": {
                "id": sid, "name": name,
                "latitude": lat, "longitude": lng,
                "distance_km": dist,
            },
            "raw_weight": weight,
            "weight": weight,
        }
        for sid, name, lat, lng, dist, weight in stations_with_weight
    ]


def _make_points(count=80, obs_per_point=2500):
    """Build fake yearly cloud points with given obs counts."""
    return [{"label": str(1940 + i), "obs_count": obs_per_point} for i in range(count)]


def _make_lightning_points(count=80, obs_per_point=2500):
    """Build fake yearly lightning points."""
    return [{"label": str(1940 + i), "lightning_obs_count": obs_per_point} for i in range(count)]


# ---------------------------------------------------------------------------
# Independent quality per dimension
# ---------------------------------------------------------------------------

def test_quality_returns_cloud_and_lightning_sections():
    """compute_quality must return separate 'cloud' and 'lightning' dicts."""
    from quality import compute_quality

    cloud_sd = _make_station_data([("C1", "Near", 59.35, 18.10, 5.0, 1.0)])
    lightning_sd = _make_station_data([("W1", "Near", 59.34, 18.08, 3.0, 1.0)])

    result = compute_quality(
        _make_points(), _make_lightning_points(), "year",
        cloud_sd, lightning_sd,
        59.33, 18.07,
    )

    assert "cloud" in result, "Must have cloud quality section"
    assert "lightning" in result, "Must have lightning quality section"
    assert "station_coverage" in result["cloud"]
    assert "historical_data" in result["cloud"]
    assert "station_coverage" in result["lightning"]
    assert "historical_data" in result["lightning"]


def test_quality_overall_is_worst_factor():
    """Overall level must equal the worst factor across both dimensions."""
    from quality import compute_quality

    # Cloud: close station → good
    cloud_sd = _make_station_data([("C1", "Near", 59.35, 18.10, 5.0, 1.0)])
    # Lightning: very far station → poor
    lightning_sd = _make_station_data([("W1", "Far", 65.0, 20.0, 500.0, 1.0)])

    result = compute_quality(
        _make_points(), _make_lightning_points(), "year",
        cloud_sd, lightning_sd,
        59.33, 18.07,
    )

    assert result["level"] == "low", (
        f"Overall should be 'low' due to poor lightning coverage, got '{result['level']}'"
    )


def test_quality_no_lightning_stations_caps_at_medium():
    """When there are no lightning stations, overall must be at most 'medium'."""
    from quality import compute_quality

    cloud_sd = _make_station_data([("C1", "Near", 59.35, 18.10, 5.0, 1.0)])

    result = compute_quality(
        _make_points(), [], "year",
        cloud_sd, [],  # no lightning stations
        59.33, 18.07,
    )

    assert result["level"] in ("low", "medium"), (
        f"With no lightning stations, overall should be at most 'medium', got '{result['level']}'"
    )
    assert result["lightning"]["station_coverage"]["level"] == "poor"


# ---------------------------------------------------------------------------
# Station coverage grading
# ---------------------------------------------------------------------------

def test_quality_close_station_is_good():
    """A single station at ~5 km should get 'good' proximity."""
    from quality import compute_quality

    sd = _make_station_data([("S1", "Close", 59.35, 18.10, 5.0, 1.0)])
    result = compute_quality(
        _make_points(), _make_lightning_points(), "year",
        sd, sd, 59.33, 18.07,
    )

    assert result["cloud"]["station_coverage"]["level"] == "good"


def test_quality_far_station_is_poor():
    """A single station at ~150 km should get 'poor' proximity."""
    from quality import compute_quality

    sd = _make_station_data([("S1", "Far", 60.50, 20.0, 150.0, 1.0)])
    result = compute_quality(
        _make_points(), _make_lightning_points(), "year",
        sd, sd, 59.33, 18.07,
    )

    assert result["cloud"]["station_coverage"]["level"] == "poor"


def test_quality_dominant_station_overrides_direction():
    """When one station has ≥85% weight, directional coverage should be 'good'.

    Regression: previously, a single station clustered in one direction would
    get penalised for poor angular spread, even though interpolation is not
    meaningful with a single dominant source.
    """
    from quality import compute_quality

    # One dominant station (weight=0.95) close by
    sd = _make_station_data([
        ("S1", "Dominant", 59.35, 18.10, 5.0, 0.95),
        ("S2", "Minor",    59.50, 18.30, 20.0, 0.05),
    ])
    result = compute_quality(
        _make_points(), _make_lightning_points(), "year",
        sd, sd, 59.33, 18.07,
    )

    # Even though both stations are in the same direction, the dominant
    # station override should give "good" coverage
    assert result["cloud"]["station_coverage"]["level"] == "good"


# ---------------------------------------------------------------------------
# Historical data grading
# ---------------------------------------------------------------------------

def test_quality_full_coverage_is_good():
    """All points with high obs counts should yield 'good' historical data."""
    from quality import compute_quality

    sd = _make_station_data([("S1", "Near", 59.35, 18.10, 5.0, 1.0)])
    pts = _make_points(count=80, obs_per_point=2500)
    lpts = _make_lightning_points(count=80, obs_per_point=2500)

    result = compute_quality(pts, lpts, "year", sd, sd, 59.33, 18.07)
    assert result["cloud"]["historical_data"]["level"] == "good"


def test_quality_sparse_data_is_poor():
    """Points with zero observations should yield 'poor' historical data."""
    from quality import compute_quality

    sd = _make_station_data([("S1", "Near", 59.35, 18.10, 5.0, 1.0)])
    # 80 points but all with 0 observations
    pts = _make_points(count=80, obs_per_point=0)
    lpts = _make_lightning_points(count=80, obs_per_point=0)

    result = compute_quality(pts, lpts, "year", sd, sd, 59.33, 18.07)
    assert result["cloud"]["historical_data"]["level"] == "poor"


def test_quality_empty_points():
    """No data points at all should return the empty quality sentinel."""
    from quality import compute_quality, EMPTY_QUALITY

    sd = _make_station_data([("S1", "Near", 59.35, 18.10, 5.0, 1.0)])
    result = compute_quality([], [], "year", sd, [], 59.33, 18.07)

    # Should still have valid structure
    assert "level" in result
    assert "cloud" in result
    assert "lightning" in result
