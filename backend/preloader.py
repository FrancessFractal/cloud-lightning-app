"""Background pre-loader for SMHI station data.

Downloads and pre-computes aggregated data for all active cloud-coverage
stations so that any user query is served from cache.

The pre-loader runs in a daemon thread started on server boot.  It:
  1. Downloads all CSV files in parallel (skipping already-cached ones).
  2. Pre-aggregates each station at all three resolutions (day/month/year).

Typical run time: ~5 minutes for the initial download of ~216 CSVs
(~1 GB), then ~90 seconds for aggregation.  Subsequent runs (within
the 7-day cache window) complete in seconds since everything is cached.

The pre-loader deliberately uses a low thread count (4 workers) and
yields between batches so it never starves the Flask server of resources.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from smhi_client import (
    PARAM_CLOUD_COVERAGE,
    PARAM_PRESENT_WEATHER,
    fetch_station_csv,
    fetch_station_list,
)

logger = logging.getLogger(__name__)

# Keep concurrency low so user requests aren't starved.
_MAX_WORKERS = 4

# ---------------------------------------------------------------------------
# State (read-only from outside)
# ---------------------------------------------------------------------------

_status: dict = {
    "state": "idle",       # idle | downloading | aggregating | ready | error
    "total_stations": 0,
    "csv_done": 0,
    "agg_done": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_lock = threading.Lock()


def get_preload_status() -> dict:
    """Return a snapshot of the pre-loader's current state."""
    with _lock:
        return dict(_status)


def _set(key, value):
    with _lock:
        _status[key] = value


# ---------------------------------------------------------------------------
# Pre-load logic
# ---------------------------------------------------------------------------


def _download_csvs(station_ids: list[str]) -> None:
    """Download all CSVs to disk in parallel, updating progress.

    Only downloads to the file cache — does NOT parse into memory.
    This avoids holding ~1 GB of parsed rows in the process.
    """
    _set("state", "downloading")

    tasks = []
    for sid in station_ids:
        tasks.append((PARAM_CLOUD_COVERAGE, sid))
        tasks.append((PARAM_PRESENT_WEATHER, sid))

    done = 0

    def _fetch(param_id, sid):
        nonlocal done
        try:
            fetch_station_csv(param_id, sid)
        except Exception as e:
            logger.warning("CSV fetch failed: param=%d station=%s: %s", param_id, sid, e)
        done += 1
        _set("csv_done", done)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = [pool.submit(_fetch, p, s) for p, s in tasks]
        for f in as_completed(futures):
            f.result()


def _aggregate_stations(station_ids: list[str]) -> None:
    """Pre-compute result caches for all resolutions.

    Import get_station_weather_data here (not at module level) to
    avoid circular import issues and keep memory tidy.
    """
    from weather import get_station_weather_data, VALID_RESOLUTIONS

    _set("state", "aggregating")

    done = 0
    for sid in station_ids:
        for res in VALID_RESOLUTIONS:
            try:
                get_station_weather_data(sid, res)
            except Exception as e:
                logger.warning("Aggregation failed: station=%s res=%s: %s", sid, res, e)
        done += 1
        _set("agg_done", done)
        # Yield briefly every station so the main thread can serve requests.
        time.sleep(0.01)


def _run_preload() -> None:
    """Main pre-load loop — runs in background thread."""
    # Give Flask a moment to finish booting before we start heavy I/O.
    time.sleep(2)

    try:
        logger.info("Pre-loader: fetching station list…")
        cloud_stations = fetch_station_list(PARAM_CLOUD_COVERAGE)
        active_ids = [s["key"] for s in cloud_stations if s.get("active")]
        _set("total_stations", len(active_ids))

        logger.info("Pre-loader: downloading CSVs for %d stations…", len(active_ids))
        t0 = time.time()
        _download_csvs(active_ids)
        logger.info("Pre-loader: CSV download done in %.1fs", time.time() - t0)

        logger.info("Pre-loader: aggregating…")
        t0 = time.time()
        _aggregate_stations(active_ids)
        logger.info("Pre-loader: aggregation done in %.1fs", time.time() - t0)

        _set("state", "ready")
        _set("finished_at", time.time())
        logger.info("Pre-loader: complete.")

    except Exception as e:
        logger.exception("Pre-loader failed: %s", e)
        _set("state", "error")
        _set("error", str(e))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_preload() -> None:
    """Launch the pre-loader in a background daemon thread.

    Safe to call multiple times — subsequent calls are no-ops if the
    pre-loader is already running or has finished.
    """
    with _lock:
        if _status["state"] != "idle":
            return
        _status["state"] = "starting"
        _status["started_at"] = time.time()

    t = threading.Thread(target=_run_preload, daemon=True, name="smhi-preloader")
    t.start()
