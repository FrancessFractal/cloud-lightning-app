"""Address geocoding via Nominatim (OpenStreetMap).

Independent of SMHI -- converts address strings to coordinates.
"""

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "weather-app/1.0"}

# Sweden bounding box (used to bias autocomplete results)
_SWEDEN_VIEWBOX = "10.9,55.3,24.2,69.1"


def geocode_address(query: str) -> dict | None:
    """Geocode an address string.

    Returns dict with ``lat``, ``lng``, ``display_name``, or None if not found.
    """
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers=_HEADERS,
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


def autocomplete_address(query: str, limit: int = 5) -> list[dict]:
    """Return up to *limit* place suggestions for a partial query.

    Biased toward Sweden for better relevance.
    Returns list of ``{lat, lng, display_name}`` dicts.
    """
    resp = requests.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "json",
            "limit": limit,
            "countrycodes": "se",
            "viewbox": _SWEDEN_VIEWBOX,
            "bounded": 0,  # prefer but don't restrict to viewbox
        },
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return [
        {
            "lat": float(hit["lat"]),
            "lng": float(hit["lon"]),
            "display_name": hit["display_name"],
        }
        for hit in resp.json()
    ]
