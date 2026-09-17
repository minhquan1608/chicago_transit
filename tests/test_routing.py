"""
@file test_routing.py
@brief Kịch bản kiểm thử (Unit Tests) cho dịch vụ định tuyến cốt lõi (RoutePlanner).
@author Lê Phước Minh Quân
@date 2026-09-18
@details File này tập trung kiểm thử logic của lớp RoutePlanner nằm trong backend.
         Sử dụng thư viện `unittest.mock` để giả lập (mock) luồng gọi tiến trình con (subprocess) 
         xuống thuật toán C++, giúp cô lập bài test và không cần chạy lõi C++ thực tế.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

from backend.api.services.routing import RoutePlanner


# ==========================================
# CẤU HÌNH BIẾN TOÀN CỤC & MOCK CLASSES
# ==========================================

# Múi giờ mặc định cho hệ thống giao thông Chicago
TZ = ZoneInfo("America/Chicago")


class FakeBoundary:
    """
    @brief Lớp giả lập ranh giới địa lý.
    @details Cung cấp phương thức `contains` để kiểm tra nhanh tọa độ có nằm trong 
             khu vực cho phép định tuyến hay không.
    """
    generated_at = "2026-04-07T00:00:00+00:00"

    def contains(self, lat: float, lon: float) -> bool:
        """
        @brief Kiểm tra tọa độ (lat, lon) có hợp lệ không.
        """
        return 41.6 <= lat <= 42.1 and -87.9 <= lon <= -87.5


class FakeRailAssets:
    """
    @brief Lớp giả lập dữ liệu trạm tàu (CTA Rail).
    @details Cung cấp thông tin tĩnh về màu sắc các tuyến và mock phương thức tìm trạm.
    """
    generated_at = "2026-04-07T00:00:00+00:00"
    line_colors = {"Red": "#C60C30", "Blue": "#00A1DE"}
    
    def resolve_station(self, stop_name: str, line_id: str | None = None):
        """
        @brief Tra cứu thông tin trạm tàu dựa trên tên.
        @param stop_name Tên trạm cần tìm (vd: "Howard").
        @return Dictionary chứa dữ liệu trạm hoặc None nếu không tìm thấy.
        """
        if stop_name == "Howard":
            return {"stop_id": "40900", "stop_name": "Howard", "routes": ["Red"]}
        return None
        

# ==========================================
# CÁC HÀM TIỆN ÍCH & TEST CASES
# ==========================================

def build_planner() -> RoutePlanner:
    """
    @brief Hàm tiện ích để khởi tạo đối tượng RoutePlanner với các dependency giả lập.
    @return Trả về một instance của RoutePlanner sẵn sàng cho việc kiểm thử.
    """
    return RoutePlanner(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        timezone_name="America/Chicago",
        candidate_limit=3,
    )


def test_outside_city_points_raise_value_error():
    """
    @brief Kiểm thử ngoại lệ khi người dùng nhập tọa độ nằm ngoài thành phố.
    @details Đảm bảo rằng hàm `plan` sẽ ném ra lỗi ValueError trước khi gọi xuống lõi C++ 
             nếu điểm bắt đầu hoặc kết thúc không nằm trong ranh giới `FakeBoundary`.
    """
    planner = build_planner()
    try:
        # Tọa độ 42.4 vượt quá giới hạn latitude 42.1 của FakeBoundary
        asyncio.run(planner.plan((42.4, -87.63), (41.79, -87.6), "walk", datetime(2026, 4, 7, 8, 0, tzinfo=TZ)))
    except ValueError as exc:
        assert "ranh giới thành phố Chicago" in str(exc)
    else:
        raise AssertionError("Expected ValueError for outside-city point.")


def test_valid_route_returns_response():
    """
    @brief Kiểm thử chức năng định tuyến thành công.
    @details Sử dụng `unittest.mock.patch` để chặn lệnh `subprocess.run` (vốn dùng để gọi C++).
             Thay vì chạy C++ thật, ta tiêm (inject) một chuỗi JSON giả lập vào `stdout`.
             Test này đảm bảo RoutePlanner phân tích cú pháp (parse) kết quả JSON từ C++ 
             thành đối tượng RouteResponse chính xác.
    """
    planner = build_planner()
    
    # Kết quả JSON giả lập trả về từ lõi C++
    fake_json = {
        "total_time": 600,
        "total_distance": 1200,
        "path": [
            {"lat": 41.88, "lon": -87.63, "type": 0},
            {"lat": 41.89, "lon": -87.62, "type": 0}
        ]
    }
    
    # Tạo một đối tượng MagicMock để thay thế kết quả trả về của subprocess.run
    mock_run = MagicMock()
    mock_run.stdout = json.dumps(fake_json)
    
    # Bắt (patch) hàm subprocess.run và ép nó trả về mock_run
    with patch("subprocess.run", return_value=mock_run):
        result = asyncio.run(planner.plan(
            (41.88, -87.63), 
            (41.89, -87.62), 
            "walk", 
            datetime(2026, 4, 7, 8, 0, tzinfo=TZ)
        ))
        
    # Xác minh (assert) dữ liệu sau khi được RoutePlanner xử lý
    assert result.totals.total_sec == 600
    assert result.totals.total_distance_m > 1000
    assert len(result.segments) > 0
    assert result.segments[0].kind == "walk"
