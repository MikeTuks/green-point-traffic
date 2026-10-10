"""TomTom Calculate Route wrapper.

The request URL contains the home coordinates (path) and the API key
(query string), so it must never reach a log. Every failure is re-raised
as a TomTomError carrying only the direction, status code and TomTom's
error code.
"""
import requests

BASE = "https://api.tomtom.com/routing/1/calculateRoute"


class TomTomError(Exception):
    pass


def route_points(home, dest, waypoints, direction):
    """Return the ordered 'lat,lon' points for one direction.

    `waypoints` is a ':'-joined string, already ordered for that direction.
    """
    middle = [p for p in waypoints.split(":") if p]
    ends = (home, dest) if direction == "outbound" else (dest, home)
    return [ends[0], *middle, ends[1]]


def calculate_route(api_key, points, direction, full_geometry=False):
    """Call Calculate Route with live traffic and all travel-time variants.

    Returns a dict with status 'ok' and the three travel times, or status
    'no_route' when TomTom finds no route (e.g. Beach Rd closed for a race).
    With full_geometry=True the raw response is included under 'raw' (for
    local route checks only; never stored).
    """
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car",
        "routeType": "fastest",
        "computeTravelTimeFor": "all",
        "routeRepresentation": "polyline" if full_geometry else "summaryOnly",
    }
    url = f"{BASE}/{':'.join(points)}/json"
    try:
        resp = requests.get(url, params=params, timeout=20)
    except requests.RequestException as e:
        raise TomTomError(f"{direction}: request failed ({type(e).__name__})") from None

    if resp.status_code != 200:
        code = _error_code(resp)
        if "NO_ROUTE" in code or "UNREACHABLE" in code:
            return {"status": "no_route"}
        raise TomTomError(f"{direction}: HTTP {resp.status_code} {code}") from None

    data = resp.json()
    summary = data["routes"][0]["summary"]
    result = {
        "status": "ok",
        "live_s": summary["liveTrafficIncidentsTravelTimeInSeconds"],
        "historic_s": summary["historicTrafficTravelTimeInSeconds"],
        "no_traffic_s": summary["noTrafficTravelTimeInSeconds"],
    }
    if full_geometry:
        result["raw"] = data
    return result


def _error_code(resp):
    try:
        err = resp.json()
    except ValueError:
        return "unknown"
    detailed = err.get("detailedError") or {}
    return str(detailed.get("code") or err.get("error", {}).get("code") or "unknown")
