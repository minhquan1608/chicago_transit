from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

from shapely.geometry import LineString, Point, shape

from backend.api.services.rail_assets import haversine_meters


def meters_to_degrees(meters: float) -> float:
    return float(meters) / 111_000


def segment_geometry(segment: Any) -> LineString | Point:
    coordinates = (getattr(segment, "geometry", {}) or {}).get("coordinates") or []
    if len(coordinates) >= 2:
        return LineString(coordinates)
    start = getattr(segment, "start", None)
    end = getattr(segment, "end", None)
    if start and end:
        if start.lat == end.lat and start.lon == end.lon:
            return Point(start.lon, start.lat)
        return LineString([(start.lon, start.lat), (end.lon, end.lat)])
    if start:
        return Point(start.lon, start.lat)
    return Point(0, 0)


def segment_distance_m(segment: Any) -> float:
    raw = float(getattr(segment, "distance_m", 0) or 0)
    if raw > 0:
        return raw
    geometry = segment_geometry(segment)
    if isinstance(geometry, Point):
        return 0.0
    coords = list(geometry.coords)
    distance = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        distance += haversine_meters(lat1, lon1, lat2, lon2)
    return distance


def overlap_ratio(geometry: LineString | Point, masked_geometry: Any) -> float:
    if geometry.is_empty or masked_geometry.is_empty:
        return 0.0
    if isinstance(geometry, Point):
        return 1.0 if masked_geometry.covers(geometry) else 0.0
    if geometry.length <= 0:
        return 1.0 if masked_geometry.covers(Point(geometry.coords[0])) else 0.0
    try:
        intersection = geometry.intersection(masked_geometry)
    except Exception:
        return 0.0
    if intersection.is_empty:
        return 0.0
    if hasattr(intersection, "length"):
        return min(1.0, max(0.0, float(intersection.length) / float(geometry.length)))
    return 1.0


@dataclass
class ContextualFactorsStore:
    asset_path: Path
    timezone_name: str

    def _load_raw(self) -> dict[str, Any]:
        with self.asset_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def raw(self) -> dict[str, Any]:
        return self._load_raw()

    @cached_property
    def metadata(self) -> dict[str, Any]:
        return self.raw.get("metadata", {})

    @cached_property
    def generated_at(self) -> str:
        return self.metadata.get("generated_at", "")

    @cached_property
    def time_profiles(self) -> list[dict[str, Any]]:
        return list(self.raw.get("time_profiles", []))

    @cached_property
    def congestion_corridors(self) -> dict[str, Any]:
        return self.raw.get("congestion_corridors", {"type": "FeatureCollection", "features": []})

    @cached_property
    def hazard_zones(self) -> dict[str, Any]:
        return self.raw.get("hazard_zones", {"type": "FeatureCollection", "features": []})

    @cached_property
    def _prepared_corridors(self) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for feature in self.congestion_corridors.get("features", []):
            props = feature.get("properties", {})
            geometry = shape(feature.get("geometry"))
            buffer_m = float(props.get("buffer_m", 90))
            prepared.append(
                {
                    "label": props.get("label", "Hành lang ùn tắc"),
                    "mode": props.get("mode", "walk"),
                    "severity": float(props.get("severity", 0.2)),
                    "active_buckets": list(props.get("active_buckets", [])),
                    "geometry": geometry.buffer(meters_to_degrees(buffer_m)),
                }
            )
        return prepared

    @cached_property
    def _prepared_hazards(self) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for feature in self.hazard_zones.get("features", []):
            props = feature.get("properties", {})
            geometry = shape(feature.get("geometry"))
            buffer_m = float(props.get("buffer_m", 60))
            prepared.append(
                {
                    "label": props.get("label", "Khu vực cần cảnh báo"),
                    "mode": props.get("mode", "road"),
                    "severity": float(props.get("severity", 0.3)),
                    "issue": props.get("issue", "hazard"),
                    "warning": props.get("warning", "Khu vực cần chú ý khi di chuyển."),
                    "geometry": geometry.buffer(meters_to_degrees(buffer_m)),
                }
            )
        return prepared

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def active_time_profile(self, depart_at) -> dict[str, Any]:
        local = depart_at.astimezone(self.timezone)
        hour = local.hour
        for profile in self.time_profiles:
            start_hour = int(profile.get("start_hour", 0))
            end_hour = int(profile.get("end_hour", 24))
            if start_hour <= end_hour:
                if start_hour <= hour < end_hour:
                    return profile
            elif hour >= start_hour or hour < end_hour:
                return profile
        return self.time_profiles[0] if self.time_profiles else {
            "id": "default",
            "label": "Mặc định",
            "walk_multiplier": 1.0,
        }

    def evaluate_candidate(self, candidate: Any) -> dict[str, Any]:
        profile = self.active_time_profile(candidate.depart_at)
        walk_multiplier = float(profile.get("walk_multiplier", 1.0))

        traffic_penalty_sec = 0
        weather_penalty_sec = 0
        congestion_alerts: set[str] = set()
        hazard_alerts: set[str] = set()
        warning_areas: set[str] = set()

        for segment in candidate.segments:
            if getattr(segment, "kind", "") != "walk":
                continue
            geometry = segment_geometry(segment)
            for corridor in self._prepared_corridors:
                corridor_mode = corridor["mode"]
                if corridor_mode not in {"all", getattr(segment, "kind", "")}:
                    continue
                if corridor["active_buckets"] and profile.get("id") not in corridor["active_buckets"]:
                    continue
                ratio = overlap_ratio(geometry, corridor["geometry"])
                if ratio <= 0:
                    continue
                multiplier = walk_multiplier
                penalty = int(round(getattr(segment, "duration_sec", 0) * ratio * corridor["severity"] * multiplier))
                if penalty > 0:
                    traffic_penalty_sec += penalty
                    congestion_alerts.add(corridor["label"])
                    warning_areas.add(corridor["label"])

            for hazard in self._prepared_hazards:
                hazard_mode = hazard["mode"]
                if hazard_mode not in {"all", "road", getattr(segment, "kind", "")}:
                    continue
                ratio = overlap_ratio(geometry, hazard["geometry"])
                if ratio <= 0:
                    continue
                penalty_factor = 0.8
                penalty = int(round(getattr(segment, "duration_sec", 0) * ratio * hazard["severity"] * penalty_factor))
                if penalty > 0:
                    weather_penalty_sec += penalty
                    hazard_alerts.add(hazard["warning"])
                    warning_areas.add(hazard["label"])

        context_penalty_sec = traffic_penalty_sec + weather_penalty_sec
        return {
            "traffic_bucket_id": str(profile.get("id", "")),
            "traffic_bucket_label": str(profile.get("label", "")),
            "context_penalty_sec": context_penalty_sec,
            "traffic_penalty_sec": traffic_penalty_sec,
            "weather_penalty_sec": weather_penalty_sec,
            "congestion_alerts": sorted(congestion_alerts),
            "hazard_alerts": sorted(hazard_alerts),
            "warning_areas": sorted(warning_areas),
            # OTP uses OSM routing and already respects one-way constraints for road vehicles.
            "one_way_compliant": True,
        }
