"""
@file rail_assets.py
@brief Quản lý cơ sở dữ liệu tài nguyên đường sắt (CTA Rail Assets) và chuẩn hóa tên trạm.
@author Lê Phước Minh Quân & others
@date 2026-09-18
@details File này chứa các tiện ích chuẩn hóa tên trạm dừng, tính toán khoảng cách cầu 
         (Haversine meters), và lớp RailAssetStore để tải, tra cứu, ánh xạ thông tin 
         các tuyến đường sắt (lines) và trạm trung chuyển (stations) của hệ thống CTA Chicago.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any


def normalize_station_name(name: str) -> str:
    """
    @brief Chuẩn hóa tên trạm dừng (loại bỏ khoảng trắng thừa, ký tự đặc biệt, viết thường).
    @details Giúp việc so khớp tên trạm trở nên linh hoạt hơn, tránh lỗi lệch định dạng chuỗi.
    @param name Tên trạm gốc cần chuẩn hóa.
    @return Chuỗi tên trạm sau khi đã làm sạch.
    """
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
    """
    @brief Tính khoảng cách đường chim bay theo công thức Haversine trên mặt cầu Trái Đất.
    @param lat1 Vĩ độ điểm 1 (độ).
    @param lon1 Kinh độ điểm 1 (độ).
    @param lat2 Vĩ độ điểm 2 (độ).
    @param lon2 Kinh độ điểm 2 (độ).
    @return Khoảng cách thực tế tính bằng mét (m).
    """
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class RailAssetStore:
    """
    @brief Kho lưu trữ và quản lý tài nguyên đường sắt đô thị (CTA Rail).
    @details Đọc thông tin các tuyến đường và danh sách trạm từ file JSON, 
             cung cấp các phương thức tra cứu và phân giải tên trạm theo ID tuyến.
    """
    lines_path: Path    # Đường dẫn đến file chứa dữ liệu các tuyến đường (GeoJSON/JSON)
    stations_path: Path # Đường dẫn đến file chứa danh sách các trạm dừng (JSON)

    def _load_json(self, path: Path) -> Any:
        """
        @brief Đọc dữ liệu JSON từ một tệp bất kỳ.
        """
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def lines(self) -> dict[str, Any]:
        """
        @brief Lưu cache dữ liệu cấu trúc các tuyến đường.
        """
        return self._load_json(self.lines_path)

    @cached_property
    def stations(self) -> list[dict[str, Any]]:
        """
        @brief Lưu cache danh sách toàn bộ các trạm dừng.
        """
        return self._load_json(self.stations_path)

    @cached_property
    def generated_at(self) -> str:
        """
        @brief Trích xuất thời điểm khởi tạo dữ liệu dòng sắt.
        """
        meta = self.lines.get("metadata", {})
        return meta.get("generated_at", "")

    @cached_property
    def line_colors(self) -> dict[str, str]:
        """
        @brief Xây dựng bảng ánh xạ màu sắc chính thức cho từng tuyến đường (vd: Red, Blue).
        """
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
        """
        @brief Tạo bảng chỉ mục (index) tra cứu trạm theo tên đã được chuẩn hóa.
        """
        index: dict[str, list[dict[str, Any]]] = {}
        for station in self.stations:
            index.setdefault(normalize_station_name(station["stop_name"]), []).append(station)
        return index

    def resolve_station(self, stop_name: str, line_id: str | None = None) -> dict[str, Any] | None:
        """
        @brief Phân giải và tìm kiếm thông tin chi tiết của một trạm dựa vào tên và mã tuyến (tùy chọn).
        @param stop_name Tên trạm cần tìm.
        @param line_id Mã tuyến đường (ví dụ: "Red", "Blue") để thu hẹp kết quả nếu trạm giao tuyến.
        @return Dictionary chứa thông tin trạm hoặc None nếu không tìm thấy.
        """
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
