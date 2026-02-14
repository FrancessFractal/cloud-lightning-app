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
    fetch_station_csv,
    parse_smhi_csv,
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

    Reads CSV from the file cache (or downloads first), parses it, and
    returns the rows.  Parsed data is NOT kept in memory — it's discarded
    after aggregation so that only one station's data is in RAM at a time.

    Returns (cloud_rows, weather_rows, has_lightning_data).
    Each row is a dict with keys: date, time, value, quality.
    """
    cloud_rows = []
    try:
        csv_text = fetch_station_csv(PARAM_CLOUD_COVERAGE, station_id)
        cloud_rows = parse_smhi_csv(csv_text)
    except requests.HTTPError:
        pass

    weather_rows = []
    has_lightning_data = False
    try:
        csv_text = fetch_station_csv(PARAM_PRESENT_WEATHER, station_id)
        weather_rows = parse_smhi_csv(csv_text)
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


def _download_csvs_for_param(param_id: int, station_ids: list[str]) -> None:
    """Download CSVs for multiple stations in parallel (disk only).

    Only downloads to the file cache — does NOT parse into memory.
    """
    def _fetch(sid):
        try:
            fetch_station_csv(param_id, sid)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_fetch, s) for s in station_ids]
        for f in as_completed(futures):
            f.result()


# ---------------------------------------------------------------------------
# Blending helpers
# ---------------------------------------------------------------------------


def _blend_cloud_point(label, entries):
    """Blend cloud coverage for one data point. entries = [(weight, pt), ...]"""
    total = 0.0
    w_sum = 0.0
    obs = 0
    for w, pt in entries:
        obs += pt.get("obs_count", 0)
        if pt["cloud_coverage_avg"] is not None:
            total += pt["cloud_coverage_avg"] * w
            w_sum += w
    return {
        "label": label,
        "cloud_coverage_avg": round(total / w_sum, 1) if w_sum > 0 else None,
        "obs_count": obs,
    }


def _blend_lightning_point(label, entries):
    """Blend lightning fields for one data point. entries = [(weight, pt), ...]"""
    prob_sum = 0.0
    prob_w = 0.0
    lower_sum = 0.0
    lower_w = 0.0
    upper_sum = 0.0
    upper_w = 0.0
    obs = 0
    for w, pt in entries:
        obs += pt.get("obs_count", 0)
        if pt["lightning_probability"] is not None:
            prob_sum += pt["lightning_probability"] * w
            prob_w += w
        if pt.get("lightning_lower") is not None:
            lower_sum += pt["lightning_lower"] * w
            lower_w += w
        if pt.get("lightning_upper") is not None:
            upper_sum += pt["lightning_upper"] * w
            upper_w += w
    return {
        "label": label,
        "lightning_probability": round(prob_sum / prob_w, 2) if prob_w > 0 else None,
        "lightning_lower": round(lower_sum / lower_w, 2) if lower_w > 0 else None,
        "lightning_upper": round(upper_sum / upper_w, 2) if upper_w > 0 else None,
        "lightning_obs_count": obs,
    }


def _blend_fixed_cloud(station_data):
    """Blend cloud data from stations with a fixed number of points (day/month)."""
    num_points = len(station_data[0]["data"]["points"])
    points = []
    for idx in range(num_points):
        label = station_data[0]["data"]["points"][idx]["label"]
        entries = [(sd["weight"], sd["data"]["points"][idx]) for sd in station_data]
        points.append(_blend_cloud_point(label, entries))
    return points


def _blend_fixed_lightning(station_data):
    """Blend lightning data from stations with a fixed number of points (day/month)."""
    num_points = len(station_data[0]["data"]["points"])
    points = []
    for idx in range(num_points):
        label = station_data[0]["data"]["points"][idx]["label"]
        entries = [(sd["weight"], sd["data"]["points"][idx]) for sd in station_data]
        points.append(_blend_lightning_point(label, entries))
    return points


def _blend_yearly_cloud(station_data):
    """Blend cloud data for yearly resolution (variable-length point arrays)."""
    all_labels = {}
    for sd in station_data:
        for pt in sd["data"]["points"]:
            all_labels[pt["label"]] = True

    lookups = []
    for sd in station_data:
        lookup = {pt["label"]: pt for pt in sd["data"]["points"]}
        lookups.append((sd["weight"], lookup))

    points = []
    for label in sorted(all_labels.keys()):
        entries = []
        for w, lookup in lookups:
            pt = lookup.get(label)
            if pt is not None:
                entries.append((w, pt))
        points.append(_blend_cloud_point(label, entries))
    return points


def _blend_yearly_lightning(station_data):
    """Blend lightning data for yearly resolution (variable-length point arrays)."""
    all_labels = {}
    for sd in station_data:
        for pt in sd["data"]["points"]:
            all_labels[pt["label"]] = True

    lookups = []
    for sd in station_data:
        lookup = {pt["label"]: pt for pt in sd["data"]["points"]}
        lookups.append((sd["weight"], lookup))

    points = []
    for label in sorted(all_labels.keys()):
        entries = []
        for w, lookup in lookups:
            pt = lookup.get(label)
            if pt is not None:
                entries.append((w, pt))
        points.append(_blend_lightning_point(label, entries))
    return points


def _merge_points(cloud_points, lightning_points):
    """Merge blended cloud and lightning point lists into unified points.

    Cloud points are the primary axis; lightning values are joined by label.
    """
    lightning_lookup = {p["label"]: p for p in lightning_points} if lightning_points else {}

    merged = []
    for cp in cloud_points:
        lp = lightning_lookup.get(cp["label"], {})
        merged.append({
            "label": cp["label"],
            "cloud_coverage_avg": cp["cloud_coverage_avg"],
            "lightning_probability": lp.get("lightning_probability"),
            "lightning_lower": lp.get("lightning_lower"),
            "lightning_upper": lp.get("lightning_upper"),
            "obs_count": cp.get("obs_count", 0),
        })
    return merged


# ---------------------------------------------------------------------------
# Helpers for the dual pipeline
# ---------------------------------------------------------------------------


def _normalize_weights(station_data: list[dict]) -> None:
    """Normalize raw_weight → weight in-place."""
    total = sum(sd["raw_weight"] for sd in station_data)
    for sd in station_data:
        sd["weight"] = sd["raw_weight"] / total


def _fetch_station_data(selected, resolution):
    """Fetch per-station aggregated data for a list of selected stations."""
    result = []
    for sd in selected:
        try:
            data = get_station_weather_data(sd["station"]["id"], resolution)
            result.append({**sd, "data": data})
        except Exception:
            pass
    return result


def _stations_info(station_data):
    """Build the JSON-serialisable station info list."""
    return [
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


# ---------------------------------------------------------------------------
# Public: location-based weather estimation (dual pipeline)
# ---------------------------------------------------------------------------


def get_location_weather(lat: float, lng: float, resolution: str = "month") -> dict:
    """Estimate weather patterns at an exact location.

    Uses two independent station pipelines:
      - Cloud coverage: nearest stations with PARAM_CLOUD_COVERAGE
      - Lightning: nearest stations with PARAM_PRESENT_WEATHER

    Each pipeline does its own station discovery, adaptive selection, weight
    normalisation, and blending.  Results are merged into a single point
    array for the frontend.
    """
    if resolution not in VALID_RESOLUTIONS:
        resolution = "month"

    # --- 1. Station discovery (independent per parameter) --------------------
    cloud_nearby = get_nearby_stations(lat, lng, parameter_id=PARAM_CLOUD_COVERAGE, count=10)
    lightning_nearby = get_nearby_stations(lat, lng, parameter_id=PARAM_PRESENT_WEATHER, count=10)

    if not cloud_nearby:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "cloud_stations": [],
            "lightning_stations": [],
            "quality": dict(EMPTY_QUALITY),
        }

    # --- 2. Adaptive station selection (independent) -------------------------
    cloud_selected = select_stations(cloud_nearby)
    lightning_selected = select_stations(lightning_nearby) if lightning_nearby else []

    # --- 3. Parallel CSV download (deduplicated) -----------------------------
    all_ids = set()
    for sd in cloud_selected:
        if read_result_cache(sd["station"]["id"], resolution) is None:
            all_ids.add(sd["station"]["id"])
    for sd in lightning_selected:
        if read_result_cache(sd["station"]["id"], resolution) is None:
            all_ids.add(sd["station"]["id"])

    if all_ids:
        # Download both param CSVs for all stations in parallel
        tasks = []
        for sid in all_ids:
            tasks.append((PARAM_CLOUD_COVERAGE, sid))
            tasks.append((PARAM_PRESENT_WEATHER, sid))

        def _fetch(param_id, sid):
            try:
                fetch_station_csv(param_id, sid)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_fetch, p, s) for p, s in tasks]
            for f in as_completed(futures):
                f.result()

    # --- 4. Fetch per-station aggregated data --------------------------------
    cloud_data = _fetch_station_data(cloud_selected, resolution)
    lightning_data = _fetch_station_data(lightning_selected, resolution)

    if not cloud_data:
        return {
            "has_lightning_data": False,
            "resolution": resolution,
            "points": [],
            "cloud_stations": [],
            "lightning_stations": [],
            "quality": dict(EMPTY_QUALITY),
        }

    # --- 5. Normalise weights independently ----------------------------------
    _normalize_weights(cloud_data)
    if lightning_data:
        _normalize_weights(lightning_data)

    has_lightning = len(lightning_data) > 0

    # --- 6. Blend cloud and lightning independently --------------------------
    if resolution == "year":
        cloud_points = _blend_yearly_cloud(cloud_data)
        lightning_points = _blend_yearly_lightning(lightning_data) if has_lightning else []
    else:
        cloud_points = _blend_fixed_cloud(cloud_data)
        lightning_points = _blend_fixed_lightning(lightning_data) if has_lightning else []

    points = _merge_points(cloud_points, lightning_points)

    # --- 7. Quality assessment (yearly baseline, independent per dimension) --
    if resolution == "year":
        cloud_yearly_points = cloud_points
        lightning_yearly_points = lightning_points
    else:
        cloud_yearly_data = _fetch_station_data(cloud_selected, "year")
        if cloud_yearly_data:
            _normalize_weights(cloud_yearly_data)
        cloud_yearly_points = _blend_yearly_cloud(cloud_yearly_data) if cloud_yearly_data else []

        if has_lightning:
            lightning_yearly_data = _fetch_station_data(lightning_selected, "year")
            if lightning_yearly_data:
                _normalize_weights(lightning_yearly_data)
            lightning_yearly_points = _blend_yearly_lightning(lightning_yearly_data) if lightning_yearly_data else []
        else:
            lightning_yearly_points = []

    quality = compute_quality(
        cloud_yearly_points, lightning_yearly_points, "year",
        cloud_data, lightning_data,
        lat, lng,
    )

    return {
        "has_lightning_data": has_lightning,
        "resolution": resolution,
        "points": points,
        "cloud_stations": _stations_info(cloud_data),
        "lightning_stations": _stations_info(lightning_data),
        "quality": quality,
    }
