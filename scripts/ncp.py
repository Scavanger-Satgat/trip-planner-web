"""Naver Cloud Platform (NCP) Maps API wrappers: geocoding and driving directions.

stdlib-only (urllib). Both functions return None on any failure (bad address,
network error, zero results) instead of raising, so callers can degrade
gracefully rather than aborting the whole run.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
DIRECTIONS_URL = "https://maps.apigw.ntruss.com/map-direction/v1/driving"


def _get(url, key_id, key_secret, timeout=10):
    req = urllib.request.Request(url)
    req.add_header("x-ncp-apigw-api-key-id", key_id)
    req.add_header("x-ncp-apigw-api-key", key_secret)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None


def geocode(address, key_id, key_secret):
    """Look up a formal address's coordinates. Returns (lat, lng) or None.

    Only works for formal road-name/lot-number addresses, NOT business/POI
    names — the NCP Geocoding API has no place-name search.
    """
    query = urllib.parse.quote(address)
    data = _get(f"{GEOCODE_URL}?query={query}", key_id, key_secret)
    if not data:
        return None
    addresses = data.get("addresses") or []
    if not addresses:
        return None
    try:
        lat = float(addresses[0]["y"])
        lng = float(addresses[0]["x"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lng)


def driving_route(start_lat, start_lng, goal_lat, goal_lng, key_id, key_secret):
    """Real road-following driving path between two points.

    Returns a list of [lat, lng] pairs, or None on failure. NCP returns path
    points as [lng, lat] — this function swaps them to the [lat, lng]
    convention used by MAP_DATA/the page template.
    """
    url = (
        f"{DIRECTIONS_URL}?start={start_lng},{start_lat}"
        f"&goal={goal_lng},{goal_lat}"
    )
    data = _get(url, key_id, key_secret)
    if not data or data.get("code") != 0:
        return None
    try:
        raw_path = data["route"]["traoptimal"][0]["path"]
    except (KeyError, IndexError, TypeError):
        return None
    return [[point[1], point[0]] for point in raw_path]
