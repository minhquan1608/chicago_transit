from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    base_dir: Path
    static_dir: Path
    assets_dir: Path
    boundary_asset: Path
    rail_lines_asset: Path
    rail_stations_asset: Path
    contextual_factors_asset: Path
    chicago_timezone: str
    candidate_limit: int
    serve_port: int
    official_boundary_url: str
    boundary_fallback_url: str
    official_gtfs_url: str
    osm_extract_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        base_dir = Path(os.getenv("CHICAGO_ROUTER_BASE_DIR", Path(__file__).resolve().parent.parent.parent)).resolve()
        assets_dir = Path(os.getenv("CHICAGO_ROUTER_ASSETS_DIR", base_dir / "data" / "assets")).resolve()
        return cls(
            base_dir=base_dir,
            static_dir=Path(os.getenv("CHICAGO_ROUTER_STATIC_DIR", base_dir / "static")).resolve(),
            assets_dir=assets_dir,
            boundary_asset=Path(os.getenv("CHICAGO_ROUTER_BOUNDARY_ASSET", assets_dir / "boundary.geojson")).resolve(),
            rail_lines_asset=Path(os.getenv("CHICAGO_ROUTER_RAIL_LINES_ASSET", assets_dir / "cta_rail_lines.geojson")).resolve(),
            rail_stations_asset=Path(os.getenv("CHICAGO_ROUTER_RAIL_STATIONS_ASSET", assets_dir / "cta_rail_stations.json")).resolve(),
            contextual_factors_asset=Path(
                os.getenv("CHICAGO_ROUTER_CONTEXTUAL_FACTORS_ASSET", assets_dir / "contextual_factors.json")
            ).resolve(),
            chicago_timezone=os.getenv("CHICAGO_TIMEZONE", "America/Chicago"),
            candidate_limit=int(os.getenv("ROUTE_CANDIDATE_LIMIT", "3")),
            serve_port=int(os.getenv("PORT", "8000")),
            official_boundary_url=os.getenv(
                "OFFICIAL_CHICAGO_BOUNDARY_URL",
                "https://data.cityofchicago.org/api/views/qqq8-j68g/rows.json?accessType=DOWNLOAD",
            ),
            boundary_fallback_url=os.getenv(
                "CHICAGO_BOUNDARY_FALLBACK_URL",
                "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities/il/chicago.json",
            ),
            official_gtfs_url=os.getenv("OFFICIAL_CTA_GTFS_URL", "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"),
            osm_extract_url=os.getenv(
                "CHICAGO_OSM_EXTRACT_URL",
                "https://download.geofabrik.de/north-america/us/illinois-latest.osm.pbf",
            ),
        )
