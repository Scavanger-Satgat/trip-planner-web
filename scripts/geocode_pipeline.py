"""Turn a validated itinerary dict into MAP_DATA / DAY_ROUTES for the page template.

Only `stops` (the route stepper) get geocoded and placed on the map — cards
and pool entries only ever get a plain "search by name" Naver Map link (built
in render.py), matching how the original reference page worked.
"""
import ncp


def build_map_data(itinerary, ncp_key_id, ncp_key_secret):
    """Returns (map_data: dict, day_routes: dict, unresolved: list[(day_number, name)])."""
    geocode_cache = {}
    map_data = {"PLACES": {}}
    day_routes = {}
    unresolved = []

    def cached_geocode(address_hint):
        if address_hint not in geocode_cache:
            geocode_cache[address_hint] = ncp.geocode(address_hint, ncp_key_id, ncp_key_secret)
        return geocode_cache[address_hint]

    for day in itinerary.get("days", []):
        day_number = day["day_number"]
        resolved_keys = []

        for i, stop in enumerate(day.get("stops", [])):
            place_key = f"d{day_number}_s{i}"
            address_hint = stop.get("address_hint") or stop.get("name", "")
            coords = cached_geocode(address_hint)
            if coords is None:
                unresolved.append((day_number, stop.get("name", "(이름 없음)")))
                continue
            lat, lng = coords
            map_data["PLACES"][place_key] = {"lat": lat, "lng": lng, "label": stop.get("name", "")}
            resolved_keys.append(place_key)

        day_routes[day_number] = {"stops": resolved_keys}

    rental_car_day = itinerary.get("rental_car_day")
    if rental_car_day is not None and rental_car_day in day_routes:
        drive_path = _compute_drive_path(
            day_routes[rental_car_day]["stops"], map_data["PLACES"], ncp_key_id, ncp_key_secret
        )
        if drive_path is not None:
            path_key = f"DAY{rental_car_day}_DRIVE_PATH"
            map_data[path_key] = drive_path
            day_routes[rental_car_day]["drivePath"] = path_key

    return map_data, day_routes, unresolved


def _compute_drive_path(stop_keys, places, ncp_key_id, ncp_key_secret):
    """Concatenate leg-by-leg driving routes between consecutive resolved stops.

    All-or-nothing: if any leg fails, drop the whole path so the map falls
    back to a straight line through the stops instead.
    """
    if len(stop_keys) < 2:
        return None

    full_path = []
    for i in range(len(stop_keys) - 1):
        start = places[stop_keys[i]]
        goal = places[stop_keys[i + 1]]
        leg = ncp.driving_route(start["lat"], start["lng"], goal["lat"], goal["lng"], ncp_key_id, ncp_key_secret)
        if leg is None:
            return None
        full_path.extend(leg if i == 0 else leg[1:])

    return full_path
