from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape
from shapely.prepared import prep


@dataclass
class ChicagoBoundary:
    asset_path: Path

    def _load_raw(self) -> dict[str, Any]:
        with self.asset_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def feature_collection(self) -> dict[str, Any]:
        raw = self._load_raw()
        if raw.get("type") == "FeatureCollection":
            return raw
        if raw.get("type") == "Feature":
            return {"type": "FeatureCollection", "features": [raw]}
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": raw}]}

    @cached_property
    def geometry(self):
        feature = self.feature_collection["features"][0]
        return shape(feature["geometry"])

    @cached_property
    def prepared(self):
        return prep(self.geometry)

    @cached_property
    def bbox(self) -> list[float]:
        minx, miny, maxx, maxy = self.geometry.bounds
        return [minx, miny, maxx, maxy]

    @cached_property
    def source(self) -> str:
        props = self.feature_collection["features"][0].get("properties", {})
        return props.get("source", "unknown")

    @cached_property
    def generated_at(self) -> str:
        props = self.feature_collection["features"][0].get("properties", {})
        return props.get("generated_at", "")

    def contains(self, lat: float, lon: float) -> bool:
        return bool(self.prepared.contains(Point(lon, lat)) or self.geometry.touches(Point(lon, lat)))
