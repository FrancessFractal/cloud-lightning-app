# Backend — Module Overview

Flask API that serves historical cloud coverage and lightning probability data
from SMHI (Swedish Meteorological and Hydrological Institute). A user provides
an address, and the backend geocodes it, finds nearby weather stations,
fetches their historical observations, and returns a distance-weighted
climate estimate for that location.

## Module map

| Module | Responsibility | Public functions | Dependencies |
|---|---|---|---|
| `app.py` | Flask routes — HTTP request/response layer only | Routes: `/api/search`, `/api/stations`, `/api/all-stations`, `/api/location-weather`, `/api/weather-data/<id>` | `geocoding`, `stations`, `weather` |
| `weather.py` | Core business logic — per-station aggregation (day/month/year resolution) and multi-station IDW interpolation | `get_station_weather_data(station_id, resolution)`, `get_location_weather(lat, lng, resolution)` | `smhi_client`, `stations`, `quality` |
| `quality.py` | Data quality assessment — report-card model grading coverage, observation depth, station proximity, and directional coverage | `compute_quality(points, resolution, station_data, target_lat, target_lng)`, `EMPTY_QUALITY` | (none — pure computation) |
| `stations.py` | Station discovery, listing, geographic math, and adaptive station selection | `haversine_km()`, `get_nearby_stations()`, `get_all_stations()`, `select_stations()` | `smhi_client` |
| `smhi_client.py` | SMHI API data access — HTTP calls, CSV parsing, file cache | `fetch_station_list()`, `fetch_station_csv()`, `parse_smhi_csv()`, `read_result_cache(station_id, resolution)`, `write_result_cache(station_id, resolution, data)` | (external: SMHI API) |
| `geocoding.py` | Address-to-coordinates via Nominatim (OpenStreetMap) | `geocode_address()` | (external: Nominatim API) |

## Dependency flow

```
app.py
 ├── geocoding.py       → Nominatim API
 ├── stations.py        → smhi_client.py → SMHI API
 └── weather.py
      ├── smhi_client.py
      ├── stations.py
      └── quality.py    (pure computation, no external deps)
```

No circular dependencies. `smhi_client.py` and `geocoding.py` are leaf modules
with no internal dependencies.

## Key conventions

- **Constants** live in `smhi_client.py`: parameter IDs (`PARAM_CLOUD_COVERAGE`,
  `PARAM_PRESENT_WEATHER`), WMO lightning codes (`LIGHTNING_CODES`), and
  `MONTH_NAMES`.
- **File caching** is handled entirely by `smhi_client.py` under the `cache/`
  directory. Raw CSVs go in `cache/csv/`, aggregated results in
  `cache/results/` (keyed by `station_{id}_{resolution}.json`).
  Cache freshness is 7 days (`CACHE_MAX_AGE_SECONDS`).
- **Station selection** uses adaptive inverse distance weighting (power=2) with
  a 2% weight threshold and a minimum of 2 stations. The constants
  `MIN_STATIONS`, `WEIGHT_THRESHOLD`, and `MIN_DIST_KM` are in `stations.py`.
- **`app.py`** should only contain route definitions and request/response
  handling. Business logic belongs in `weather.py` or `stations.py`.

## Running locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py   # starts Flask on http://127.0.0.1:5000
```
