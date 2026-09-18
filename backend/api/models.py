"""
@file models.py
@brief Định nghĩa các Pydantic Models cho dự án Chicago Route Planner.
@author Lê Phước Minh Quân & others
@date 2026-09-18
@details File này chứa các cấu trúc dữ liệu (Schema) sử dụng Pydantic để xác thực (validate) 
         dữ liệu đầu vào (Request) từ người dùng và định dạng dữ liệu đầu ra (Response) 
         của các API RESTful trong hệ thống.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """
    @brief Cấu trúc tọa độ địa lý cơ bản.
    """
    lat: float
    lon: float


class RouteTotals(BaseModel):
    """
    @brief Tổng hợp các chỉ số chi phí của toàn bộ lộ trình.
    @details Chứa thông tin về tổng thời gian, tổng quãng đường phân tách theo 
             từng loại phương tiện, và thời gian phạt do các yếu tố môi trường.
    """
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
    """
    @brief Mô tả chi tiết một chặng di chuyển trong lộ trình tổng thể.
    @details Mỗi chặng biểu diễn một hành động di chuyển đồng nhất (chỉ đi bộ hoặc chỉ đi tàu),
             kèm theo thông tin hình học để vẽ lên bản đồ (Leaflet).
    """
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
    """
    @brief Tóm tắt thông tin tổng quan của lộ trình.
    """
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
    """
    @brief Lưu trữ thông tin ngữ cảnh môi trường ảnh hưởng đến lộ trình.
    @details Chứa thông tin phân loại giao thông hiện tại và các cảnh báo về 
             ùn tắc, ngập úng trên đoạn đường.
    """
    traffic_bucket_id: str = ""
    traffic_bucket_label: str = ""
    one_way_compliant: bool = True
    congestion_alerts: list[str] = Field(default_factory=list)
    hazard_alerts: list[str] = Field(default_factory=list)
    warning_areas: list[str] = Field(default_factory=list)


class RouteResponse(BaseModel):
    """
    @brief Cấu trúc Response trả về cho client khi tìm đường thành công.
    @details Tích hợp tất cả các thành phần: tóm tắt (summary), chỉ số (totals), 
             các chặng (segments) và ngữ cảnh (context).
    """
    summary: RouteSummary
    totals: RouteTotals
    segments: list[RouteSegment]
    context: RouteContext = Field(default_factory=RouteContext)
    warnings: list[str] = Field(default_factory=list)
    data_timestamps: dict[str, str] = Field(default_factory=dict)
    inside_city: bool = True


class BoundaryResponse(BaseModel):
    """
    @brief Cấu trúc Response cho API lấy ranh giới thành phố Chicago.
    """
    bbox: list[float]
    feature_collection: dict[str, Any]
    source: str
    generated_at: str


class RailMetaResponse(BaseModel):
    """
    @brief Cấu trúc Response cho API lấy siêu dữ liệu hệ thống đường sắt (CTA).
    """
    lines: dict[str, Any]
    stations: list[dict[str, Any]]
    generated_at: str


class ContextMetaResponse(BaseModel):
    """
    @brief Cấu trúc Response cho API lấy cấu hình ngữ cảnh môi trường.
    """
    time_profiles: list[dict[str, Any]]
    congestion_corridors: dict[str, Any]
    hazard_zones: dict[str, Any]
    generated_at: str


class BlockedSegmentInput(BaseModel):
    """
    @brief Cấu trúc Request mô tả một đoạn đường bị cấm/phong tỏa.
    """
    start: Coordinate
    end: Coordinate
    label: str | None = None
    buffer_m: float = Field(default=35, ge=10, le=200)
    geometry: dict[str, Any] | None = None


class AdvancedRouteRequest(BaseModel):
    """
    @brief Cấu trúc Request payload cho API POST `/api/route`.
    @details Nhận các thông số nâng cao từ client như danh sách điểm dừng trung gian (stops),
             chế độ sắp xếp điểm dừng (stop_order_mode) và các đoạn đường cấm thao tác thủ công.
    """
    origin: Coordinate
    destination: Coordinate
    profile: Literal["walk"] = "walk"
    depart_at: datetime | None = None
    stops: list[Coordinate] = Field(default_factory=list)
    stop_order_mode: Literal["none", "ordered", "optimize"] = "none"
    blocked_segments: list[BlockedSegmentInput] = Field(default_factory=list)
