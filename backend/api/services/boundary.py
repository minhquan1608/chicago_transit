"""
@file boundary.py
@brief Quản lý ranh giới địa lý (Boundary) của thành phố Chicago.
@author Lê Phước Minh Quân & others
@date 2026-09-18
@details File này chứa lớp ChicagoBoundary chịu trách nhiệm đọc dữ liệu GeoJSON, 
         chuyển đổi thành cấu trúc hình học (Shapely) và cung cấp các phương thức 
         kiểm tra tọa độ (lat, lon) có nằm trong thành phố hay không nhằm chặn các 
         lộ trình lỗi nằm ngoài vùng quy hoạch.
"""

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
    """
    @brief Lớp xử lý và kiểm tra ranh giới địa lý.
    @details Tự động chuẩn hóa dữ liệu đầu vào thành định dạng FeatureCollection, 
             sử dụng @cached_property để lưu trữ các thuộc tính hình học trong bộ nhớ tạm 
             giúp tối ưu hóa tốc độ truy vấn không gian (spatial queries).
    """
    
    asset_path: Path  # Đường dẫn đến file dữ liệu (thường là JSON/GeoJSON)

    def _load_raw(self) -> dict[str, Any]:
        """
        @brief Đọc dữ liệu thô từ file.
        @return Dictionary chứa dữ liệu JSON gốc.
        """
        with self.asset_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def feature_collection(self) -> dict[str, Any]:
        """
        @brief Chuẩn hóa dữ liệu thô thành định dạng chuẩn GeoJSON FeatureCollection.
        @details Xử lý các trường hợp đầu vào là FeatureCollection, Feature đơn lẻ, 
                 hoặc chỉ chứa dữ liệu Geometry thô.
        @return Một dictionary biểu diễn FeatureCollection hợp lệ.
        """
        raw = self._load_raw()
        if raw.get("type") == "FeatureCollection":
            return raw
        if raw.get("type") == "Feature":
            return {"type": "FeatureCollection", "features": [raw]}
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": raw}]}

    @cached_property
    def geometry(self):
        """
        @brief Chuyển đổi dữ liệu JSON thành đối tượng hình học (Geometry) của thư viện Shapely.
        """
        feature = self.feature_collection["features"][0]
        return shape(feature["geometry"])

    @cached_property
    def prepared(self):
        """
        @brief Khởi tạo đối tượng PreparedGeometry.
        @details Thuật toán chuẩn bị của Shapely giúp các phép toán kiểm tra giao cắt/chứa đựng 
                 (contains, intersects) nhanh hơn rất nhiều khi phải thực thi liên tục.
        """
        return prep(self.geometry)

    @cached_property
    def bbox(self) -> list[float]:
        """
        @brief Tính toán hình chữ nhật bao quanh (Bounding Box) ranh giới.
        @return Danh sách [minx, miny, maxx, maxy] tương ứng với [min_lon, min_lat, max_lon, max_lat].
        """
        minx, miny, maxx, maxy = self.geometry.bounds
        return [minx, miny, maxx, maxy]

    @cached_property
    def source(self) -> str:
        """
        @brief Trích xuất nguồn gốc (source) của dữ liệu ranh giới.
        """
        props = self.feature_collection["features"][0].get("properties", {})
        return props.get("source", "unknown")

    @cached_property
    def generated_at(self) -> str:
        """
        @brief Trích xuất mốc thời gian tạo dữ liệu (generated_at).
        """
        props = self.feature_collection["features"][0].get("properties", {})
        return props.get("generated_at", "")

    def contains(self, lat: float, lon: float) -> bool:
        """
        @brief Kiểm tra một tọa độ địa lý có nằm bên trong hoặc ngay trên rìa ranh giới không.
        @param lat Vĩ độ (Latitude).
        @param lon Kinh độ (Longitude).
        @return True nếu tọa độ hợp lệ (nằm trong Chicago), ngược lại False.
        """
        # Lưu ý: Point trong thư viện Shapely nhận tọa độ theo thứ tự (x, y) tức là (longitude, latitude)
        return bool(self.prepared.contains(Point(lon, lat)) or self.geometry.touches(Point(lon, lat)))
