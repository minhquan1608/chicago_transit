from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    lat: float
    lon: float


class RouteTotals(BaseModel):
    total_sec: int
    walk_sec: int = 0
    rail_sec: int = 0
    wait_sec: int = 0
    total_distance_m: float = 0
    walk_distance_m: float = 0
    rail_distance_m: float = 0
    context_penalty_sec: int = 0
    evaluated_sec: int = 0


class RouteSegment(BaseModel):
    kind: Literal["walk", "rail"]
    duration_sec: int
    distance_m: float = 0
    geometry: dict[str, Any]
    start: Coordinate
    end: Coordinate
    from_name: str | None = None
    to_name: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    line_id: str | None = None
    line_name: str | None = None
    line_color: str | None = None
    station_id: str | None = None


class RouteSummary(BaseModel):
    profile: Literal["walk"]
    selected_strategy: Literal["walk_only", "walk_rail"]
    description: str
    depart_at: datetime
    arrive_at: datetime | None = None
    lines_used: list[str] = Field(default_factory=list)
    stop_order_mode: Literal["none", "ordered", "optimize"] = "none"
    stop_order_indices: list[int] = Field(default_factory=list)
    blocked_segment_count: int = 0


class RouteContext(BaseModel):
    traffic_bucket_id: str = ""
    traffic_bucket_label: str = ""
    one_way_compliant: bool = True
    congestion_alerts: list[str] = Field(default_factory=list)
    hazard_alerts: list[str] = Field(default_factory=list)
    warning_areas: list[str] = Field(default_factory=list)


class RouteResponse(BaseModel):
    summary: RouteSummary
    totals: RouteTotals
    segments: list[RouteSegment]
    context: RouteContext = Field(default_factory=RouteContext)
    warnings: list[str] = Field(default_factory=list)
    data_timestamps: dict[str, str] = Field(default_factory=dict)
    inside_city: bool = True


class BoundaryResponse(BaseModel):
    bbox: list[float]
    feature_collection: dict[str, Any]
    source: str
    generated_at: str


class RailMetaResponse(BaseModel):
    lines: dict[str, Any]
    stations: list[dict[str, Any]]
    generated_at: str


class ContextMetaResponse(BaseModel):
    time_profiles: list[dict[str, Any]]
    congestion_corridors: dict[str, Any]
    hazard_zones: dict[str, Any]
    generated_at: str


class BlockedSegmentInput(BaseModel):
    start: Coordinate
    end: Coordinate
    label: str | None = None
    buffer_m: float = Field(default=35, ge=10, le=200)
    geometry: dict[str, Any] | None = None


class AdvancedRouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    profile: Literal["walk"] = "walk"
    depart_at: datetime | None = None
    stops: list[Coordinate] = Field(default_factory=list)
    stop_order_mode: Literal["none", "ordered", "optimize"] = "none"
    blocked_segments: list[BlockedSegmentInput] = Field(default_factory=list)
