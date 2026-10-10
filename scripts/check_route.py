"""Phase 0 route check (local use only, nothing is stored in the repo).

Makes one pinned call per direction and prints each leg's length and
time, so a U-turn at a waypoint shows up as an unexpectedly long leg.
Writes local/route_<direction>.geojson (git-ignored) to view on a map.

Reads TOMTOM_API, TOMTOM_HOME, TOMTOM_DEST, TOMTOM_OUT_WAYPOINTS and
TOMTOM_RET_WAYPOINTS from the environment or from .env.
"""
import json
import os
import sys
from pathlib import Path

from tomtom import calculate_route, route_points

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()
    home, dest = os.environ["TOMTOM_HOME"], os.environ["TOMTOM_DEST"]
    waypoints = {"outbound": os.environ["TOMTOM_OUT_WAYPOINTS"], "return": os.environ["TOMTOM_RET_WAYPOINTS"]}
    out_dir = ROOT / "local"
    out_dir.mkdir(exist_ok=True)

    for direction in ("outbound", "return"):
        points = route_points(home, dest, waypoints[direction], direction)
        result = calculate_route(os.environ["TOMTOM_API"], points, direction, full_geometry=True)
        if result["status"] != "ok":
            print(f"{direction}: {result['status']}")
            continue
        route = result["raw"]["routes"][0]
        print(f"\n{direction}: live {result['live_s'] / 60:.1f} min, historic {result['historic_s'] / 60:.1f} min, "
              f"no traffic {result['no_traffic_s'] / 60:.1f} min")
        coords = []
        for i, leg in enumerate(route["legs"], 1):
            s = leg["summary"]
            print(f"  leg {i}: {s['lengthInMeters'] / 1000:.2f} km, {s['travelTimeInSeconds'] / 60:.1f} min")
            coords += [[p["longitude"], p["latitude"]] for p in leg["points"]]
        geojson = {"type": "Feature", "properties": {"direction": direction},
                   "geometry": {"type": "LineString", "coordinates": coords}}
        (out_dir / f"route_{direction}.geojson").write_text(json.dumps(geojson), encoding="utf-8")
    print(f"\nRoute files written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
