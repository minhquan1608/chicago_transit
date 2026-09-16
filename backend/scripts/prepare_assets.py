#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, Point, mapping, shape

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
ASSETS_DIR = DATA_DIR / "assets"
RAW_DIR = DATA_DIR / "raw"

OFFICIAL_BOUNDARY_URL = "https://data.cityofchicago.org/api/views/qqq8-j68g/rows.json?accessType=DOWNLOAD"
FALLBACK_BOUNDARY_URL = "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities/il/chicago.json"
OFFICIAL_GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"




def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def ensure_dirs() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def normalize_boundary(raw: dict[str, Any], source_label: str) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()

    if raw.get("type") == "FeatureCollection":
        feature_collection = raw
    elif raw.get("type") == "Feature":
        feature_collection = {"type": "FeatureCollection", "features": [raw]}
    else:
        feature_collection = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": raw}]}

    feature = feature_collection["features"][0]
    properties = feature.setdefault("properties", {})
    properties["source"] = source_label
    properties["generated_at"] = generated_at
    properties["official_boundary_url"] = OFFICIAL_BOUNDARY_URL
    return feature_collection


def build_boundary_asset() -> tuple[dict[str, Any], Any]:
    raw = None
    source = "City of Chicago open data"
    try:
        raw = fetch_json(OFFICIAL_BOUNDARY_URL)
    except Exception:
        source = "US Census-derived fallback due blocked official download"
        raw = fetch_json(FALLBACK_BOUNDARY_URL)

    feature_collection = normalize_boundary(raw, source)
    geometry = shape(feature_collection["features"][0]["geometry"])
    output_path = ASSETS_DIR / "boundary.geojson"
    output_path.write_text(json.dumps(feature_collection), encoding="utf-8")
    return feature_collection, geometry


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clip_line_to_boundary(line: LineString, boundary_geometry) -> list[dict[str, Any]]:
    if not line.is_valid or line.is_empty:
        return []
    clipped = line.intersection(boundary_geometry)
    if clipped.is_empty:
        return []
    if clipped.geom_type == "LineString":
        return [mapping(clipped)]
    if clipped.geom_type == "MultiLineString":
        return [mapping(geom) for geom in clipped.geoms if not geom.is_empty]
    if clipped.geom_type == "GeometryCollection":
        return [mapping(geom) for geom in clipped.geoms if geom.geom_type == "LineString" and not geom.is_empty]
    return []


def build_rail_assets(boundary_geometry) -> None:
    routes = {row["route_id"]: row for row in load_csv(DATA_DIR / "routes.txt") if row["route_type"] == "1"}
    trips = {row["trip_id"]: row for row in load_csv(DATA_DIR / "trips.txt") if row["route_id"] in routes}
    route_shapes: dict[str, set[str]] = defaultdict(set)
    for trip in trips.values():
        route_shapes[trip["route_id"]].add(trip["shape_id"])

    shape_rows = load_csv(DATA_DIR / "shapes.txt")
    shapes: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    relevant_shape_ids = {shape_id for ids in route_shapes.values() for shape_id in ids}
    for row in shape_rows:
        shape_id = row["shape_id"]
        if shape_id not in relevant_shape_ids:
            continue
        sequence = int(row.get("shape_pt_sequence") or 0)
        lat = float(row["shape_pt_lat"])
        lon = float(row["shape_pt_lon"])
        shapes[shape_id].append((sequence, lat, lon))

    lines_features: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for route_id, shape_ids in route_shapes.items():
        route = routes[route_id]
        for shape_id in shape_ids:
            pts = sorted(shapes.get(shape_id, []), key=lambda item: item[0])
            if len(pts) < 2:
                continue
            line = LineString([(lon, lat) for _, lat, lon in pts])
            for clipped_geometry in clip_line_to_boundary(line, boundary_geometry):
                feature_key = json.dumps(clipped_geometry["coordinates"])[:2000]
                dedupe_key = f"{route_id}:{feature_key}"
                if dedupe_key in seen_hashes:
                    continue
                seen_hashes.add(dedupe_key)
                lines_features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "route_id": route_id,
                            "route_long_name": route["route_long_name"],
                            "route_color": f"#{route['route_color'].upper()}",
                            "route_text_color": f"#{route['route_text_color'].upper()}",
                            "shape_id": shape_id,
                        },
                        "geometry": clipped_geometry,
                    }
                )

    lines_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "CTA GTFS routes/shapes clipped to Chicago boundary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "features": lines_features,
    }
    (ASSETS_DIR / "cta_rail_lines.geojson").write_text(json.dumps(lines_geojson), encoding="utf-8")

    stops = load_csv(DATA_DIR / "stops.txt")
    parent_stations = {row["stop_id"]: row for row in stops if row.get("location_type") == "1"}
    stop_to_station: dict[str, str] = {}
    for row in stops:
        stop_id = row["stop_id"]
        if row.get("location_type") == "1":
            stop_to_station[stop_id] = stop_id
        elif row.get("parent_station") in parent_stations:
            stop_to_station[stop_id] = row["parent_station"]

    station_routes: dict[str, set[str]] = defaultdict(set)
    for row in load_csv(DATA_DIR / "stop_times.txt"):
        trip = trips.get(row["trip_id"])
        station_id = stop_to_station.get(row["stop_id"])
        if trip and station_id:
            station_routes[station_id].add(trip["route_id"])

    station_features: list[dict[str, Any]] = []
    for station_id, station in parent_stations.items():
        point = Point(float(station["stop_lon"]), float(station["stop_lat"]))
        if not (boundary_geometry.contains(point) or boundary_geometry.touches(point)):
            continue
        routes_for_station = sorted(station_routes.get(station_id, []))
        if not routes_for_station:
            continue
        station_features.append(
            {
                "stop_id": station_id,
                "stop_name": station["stop_name"],
                "lat": float(station["stop_lat"]),
                "lon": float(station["stop_lon"]),
                "routes": routes_for_station,
                "route_colors": {route_id: f"#{routes[route_id]['route_color'].upper()}" for route_id in routes_for_station},
            }
        )

    station_features.sort(key=lambda item: item["stop_name"])
    (ASSETS_DIR / "cta_rail_stations.json").write_text(json.dumps(station_features), encoding="utf-8")




def download_official_gtfs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RAW_DIR / "cta-official.gtfs.zip"
    request = urllib.request.Request(OFFICIAL_GTFS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        output_path.write_bytes(response.read())


def ensure_gtfs_extracted() -> str:
    if (DATA_DIR / "routes.txt").exists():
        return "used existing local GTFS text files"
    
    official_zip = RAW_DIR / "cta-official.gtfs.zip"
    if not official_zip.exists():
        print("GTFS data missing. Downloading from official CTA source...")
        download_official_gtfs()
        
    print("Extracting GTFS files...")
    with zipfile.ZipFile(official_zip, "r") as zip_ref:
        zip_ref.extractall(DATA_DIR)
    return "extracted official GTFS data"


def main() -> int:
    ensure_dirs()
    boundary_geojson, boundary_geometry = build_boundary_asset()

    try:
        gtfs_status = ensure_gtfs_extracted()
    except Exception as e:
        print(f"Failed to setup GTFS: {e}")
        return 1

    build_rail_assets(boundary_geometry)

    print(f"Boundary bbox: {shape(boundary_geojson['features'][0]['geometry']).bounds}")
    print(f"Assets written to {ASSETS_DIR}")
    print(gtfs_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
