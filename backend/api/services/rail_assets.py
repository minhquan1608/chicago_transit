from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any


def normalize_station_name(name: str) -> str:
    normalized = name.strip().lower()
    normalized = normalized.replace("wash./wabash", "washington/wabash")
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[\(\)\[\]/]", " ", normalized)
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"\bline\b", " ", normalized)
    normalized = re.sub(r"\bbranch\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class RailAssetStore:
    lines_path: Path
    stations_path: Path

    def _load_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def lines(self) -> dict[str, Any]:
        return self._load_json(self.lines_path)

    @cached_property
    def stations(self) -> list[dict[str, Any]]:
        return self._load_json(self.stations_path)

    @cached_property
    def generated_at(self) -> str:
        meta = self.lines.get("metadata", {})
        return meta.get("generated_at", "")

    @cached_property
    def line_colors(self) -> dict[str, str]:
        colors: dict[str, str] = {}
        for feature in self.lines.get("features", []):
            props = feature.get("properties", {})
            route_id = props.get("route_id")
            route_color = props.get("route_color")
            if route_id and route_color:
                colors[route_id] = route_color
        for station in self.stations:
            for route_id, route_color in station.get("route_colors", {}).items():
                colors.setdefault(route_id, route_color)
        return colors

    @cached_property
    def station_by_name(self) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for station in self.stations:
            index.setdefault(normalize_station_name(station["stop_name"]), []).append(station)
        return index

    def resolve_station(self, stop_name: str, line_id: str | None = None) -> dict[str, Any] | None:
        normalized_name = normalize_station_name(stop_name)
        candidates = self.station_by_name.get(normalized_name, [])
        if not candidates:
            loose_matches = []
            for candidate_name, stations in self.station_by_name.items():
                if normalized_name in candidate_name or candidate_name in normalized_name:
                    loose_matches.extend(stations)
            candidates = loose_matches
        if not candidates:
            return None
        if line_id:
            for candidate in candidates:
                if line_id in candidate.get("routes", []):
                    return candidate
        return candidates[0]


