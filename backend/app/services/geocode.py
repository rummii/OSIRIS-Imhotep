"""Reverse-geocoding service for GPS coordinates.

Default provider: OpenStreetMap Nominatim (no API key, public endpoint,
respects PSGC barangay/municipality/province hierarchy in the Philippines).
The endpoint is configurable so an on-prem or commercial geocoder can be swapped in.

All network calls are best-effort: any failure returns None so the caller can
fall back to raw coordinates. Results are cached in-process by a 6-decimal grid
key (~10 cm resolution) to avoid hammering the geocoder for co-located photos.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from app.models.schemas import SiteLocation

logger = logging.getLogger("osiris.geocode")

# Grid resolution for the in-process cache (~10 cm at the equator).
_CACHE_PRECISION = 6
_cache: dict[tuple[float, float], Optional[SiteLocation]] = {}


def _grid_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, _CACHE_PRECISION), round(lon, _CACHE_PRECISION))


def _parse_nominatim(payload: dict) -> Optional[SiteLocation]:
    """Translate a Nominatim reverse response into a SiteLocation."""
    if not isinstance(payload, dict):
        return None
    address = payload.get("address") or {}
    if not isinstance(address, dict):
        address = {}

    # PSGC priority mapping; fall back to OSM defaults.
    barangay = (
        address.get("village")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("neighbourhood")
        or address.get("quarter")
        or address.get("city_district")
    )
    municipality = (
        address.get("city")
        or address.get("municipality")
        or address.get("town")
        or address.get("county")
    )
    province = address.get("province") or address.get("state_district")
    region = address.get("region") or address.get("state")
    country = address.get("country")
    raw_address = payload.get("display_name")

    if not any([barangay, municipality, province, region, country, raw_address]):
        return None

    return SiteLocation(
        barangay=barangay,
        municipality=municipality,
        province=province,
        region=region,
        country=country,
        raw_address=raw_address,
    )


def reverse_geocode(
    lat: float,
    lon: float,
    endpoint: str = "https://nominatim.openstreetmap.org/reverse",
    user_agent: str = "OSIRIS-Imhotep/1.0 (engineering SOW platform)",
    timeout: float = 5.0,
    zoom: int = 18,
) -> Optional[SiteLocation]:
    """Reverse-geocode (lat, lon) to a SiteLocation.

    Returns None on any error or empty result. Cached per 6-decimal grid
    cell to avoid duplicate lookups within a site.
    """
    key = _grid_key(lat, lon)
    if key in _cache:
        return _cache[key]

    params = urllib.parse.urlencode({
        "format": "jsonv2",
        "lat": f"{lat:.7f}",
        "lon": f"{lon:.7f}",
        "zoom": str(zoom),
        "addressdetails": "1",
    })
    url = f"{endpoint.rstrip('/')}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Reverse-geocode failed for (%.5f, %.5f): %s", lat, lon, exc)
        _cache[key] = None
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Reverse-geocode returned non-JSON for (%.5f, %.5f)", lat, lon)
        _cache[key] = None
        return None

    location = _parse_nominatim(payload)
    _cache[key] = location
    logger.info(
        "Reverse-geocoded (%.5f, %.5f) -> %s in %.2fs",
        lat, lon, location.compact() if location else "(no match)", time.monotonic() - t0,
    )
    return location


def clear_cache() -> None:
    """Reset the in-process geocode cache (for tests / admin endpoints)."""
    _cache.clear()