"""Address geocoding via Nominatim (OpenStreetMap).

Independent of SMHI -- converts address strings to coordinates.
"""

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_address(query: str) -> dict | None:
    """Geocode an address string.

    Returns dict with ``lat``, ``lng``, ``display_name``, or None if not found.
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
