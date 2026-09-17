"""
@file test_api.py
@brief Kịch bản kiểm thử (Unit Tests) cho các API của Chicago Route Planner.
@author Lê Phước Minh Quân & others
@date 2026-09-18
@details File này sử dụng FastAPI TestClient để kiểm thử tự động các điểm cuối (endpoints) của API.
         Sử dụng các lớp giả lập (Mock/Fake Classes) để cách ly logic định tuyến (A*, GA) 
         khỏi việc kiểm tra luồng hoạt động của API, đảm bảo tốc độ chạy test nhanh gọn.
"""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.models import Coordinate, RouteContext, RouteResponse, RouteSegment, RouteSummary, RouteTotals


# ==========================================
# CÁC LỚP GIẢ LẬP DỮ LIỆU (MOCK CLASSES)
# ==========================================

class FakeBoundary:
    """
    @brief Lớp giả lập ranh giới địa lý của thành phố Chicago.
    @details Cung cấp một bounding box và đa giác (polygon) cố định để phục vụ cho các bài test
             kiểm tra điểm đầu/cuối có nằm trong thành phố hay không.
    """
    bbox = [-87.9, 41.6, -87.5, 42.0]
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"source": "test", "generated_at": "2026-04-07T00:00:00+00:00"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-87.9, 41.6], [-87.5, 41.6], [-87.5, 42.0], [-87.9, 42.0], [-87.9, 41.6]]],
                },
            }
        ],
    }
    source = "test"
    generated_at = "2026-04-07T00:00:00+00:00"

    def contains(self, lat: float, lon: float) -> bool:
        """
        @brief Kiểm tra tọa độ có nằm trong ranh giới giả lập hay không.
        """
        return 41.6 <= lat <= 42.0 and -87.9 <= lon <= -87.5


class FakeRailAssets:
    """
    @brief Lớp giả lập cơ sở dữ liệu hệ thống đường sắt (CTA).
    """
    lines = {"type": "FeatureCollection", "metadata": {"generated_at": "2026-04-07T00:00:00+00:00"}, "features": []}
    stations = []
    generated_at = "2026-04-07T00:00:00+00:00"


class FakeContextualFactors:
    """
    @brief Lớp giả lập các yếu tố ngữ cảnh môi trường (giao thông, thời tiết, ngập lụt).
    """
    generated_at = "2026-04-07T00:00:00+00:00"
    time_profiles = [{"id": "morning_peak", "label": "Cao điểm sáng"}]
    congestion_corridors = {"type": "FeatureCollection", "features": []}
    hazard_zones = {"type": "FeatureCollection", "features": []}


class FakePlanner:
    """
    @brief Lớp giả lập bộ định tuyến luôn trả về lỗi.
    @details Dùng để kiểm thử các kịch bản ngoại lệ (ví dụ: tọa độ nằm ngoài thành phố).
    """
    async def plan(self, origin, destination, profile, depart_at, **kwargs):
        raise ValueError("Cả hai điểm phải nằm trong ranh giới thành phố Chicago.")


class SuccessfulPlanner:
    """
    @brief Lớp giả lập bộ định tuyến thành công.
    @details Dùng để kiểm thử các kịch bản người dùng tìm đường hợp lệ.
             Lớp này lưu lại lịch sử các tham số được gọi (tại self.calls) để so sánh (assert) trong các bài test.
    """
    def __init__(self):
        self.calls = []

    async def plan(self, origin, destination, profile, depart_at, **kwargs):
        """
        @brief Trả về một RouteResponse giả lập với lộ trình đi bộ hợp lệ.
        """
        self.calls.append(
            {
                "origin": origin,
                "destination": destination,
                "profile": profile,
                "depart_at": depart_at,
                "kwargs": kwargs,
            }
        )
        return RouteResponse(
            summary=RouteSummary(
                profile=profile,
                selected_strategy="walk_only",
                description="Đi bộ toàn tuyến trong Chicago.",
                depart_at=depart_at or datetime(2026, 4, 7, 8, 0),
                arrive_at=depart_at or datetime(2026, 4, 7, 8, 0),
            ),
            totals=RouteTotals(total_sec=600, walk_sec=600, total_distance_m=1200, walk_distance_m=1200, evaluated_sec=600),
            segments=[
                RouteSegment(
                    kind="walk",
                    duration_sec=600,
                    distance_m=1200,
                    geometry={"type": "LineString", "coordinates": [[-87.63, 41.88], [-87.62, 41.89]]},
                    start=Coordinate(lat=41.88, lon=-87.63),
                    end=Coordinate(lat=41.89, lon=-87.62),
                )
            ],
            context=RouteContext(traffic_bucket_id="morning_peak", traffic_bucket_label="Cao điểm sáng"),
            warnings=[],
            data_timestamps={},
            inside_city=True,
        )


# ==========================================
# CÁC HÀM KIỂM THỬ API (UNIT TESTS)
# ==========================================

def test_boundary_meta_endpoint():
    """
    @brief Kiểm thử endpoint `/api/meta/boundary`.
    @details Đảm bảo API trả về đúng mã trạng thái HTTP 200 và dữ liệu bounding box chính xác.
    """
    app = create_app(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        contextual_factors=FakeContextualFactors(),
        planner=FakePlanner(),
    )
    client = TestClient(app)
    response = client.get("/api/meta/boundary")
    assert response.status_code == 200
    assert response.json()["bbox"] == [-87.9, 41.6, -87.5, 42.0]


def test_route_endpoint_returns_400_for_invalid_city_points():
    """
    @brief Kiểm thử lỗi 400 Bad Request trên endpoint `/api/route`.
    @details Đảm bảo API báo lỗi khi tọa độ truyền vào nằm ngoài ranh giới thành phố.
    """
    app = create_app(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        contextual_factors=FakeContextualFactors(),
        planner=FakePlanner(),
    )
    client = TestClient(app)
    response = client.get("/api/route", params={"from": "42.2,-87.7", "to": "41.8,-87.6", "profile": "walk"})
    assert response.status_code == 400
    assert "ranh giới thành phố Chicago" in response.json()["detail"]


def test_context_meta_endpoint():
    """
    @brief Kiểm thử endpoint `/api/meta/context`.
    @details Đảm bảo API trả về đúng thông tin ngữ cảnh môi trường hiện tại (vd: "morning_peak").
    """
    app = create_app(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        contextual_factors=FakeContextualFactors(),
        planner=FakePlanner(),
    )
    client = TestClient(app)
    response = client.get("/api/meta/context")
    assert response.status_code == 200
    assert response.json()["time_profiles"][0]["id"] == "morning_peak"


def test_post_route_passes_stops_and_blocked_segments():
    """
    @brief Kiểm thử luồng POST đầy đủ trên endpoint `/api/route`.
    @details Đảm bảo API nhận diện và truyền đúng các tham số nâng cao (điểm dừng - stops, 
             chiến lược sắp xếp - stop_order_mode, và các đoạn đường cấm - blocked_segments) 
             vào bộ định tuyến Planner (thuật toán GA và A*).
    """
    planner = SuccessfulPlanner()
    app = create_app(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        contextual_factors=FakeContextualFactors(),
        planner=planner,
    )
    client = TestClient(app)
    response = client.post(
        "/api/route",
        json={
            "origin": {"lat": 41.88, "lon": -87.63},
            "destination": {"lat": 41.79, "lon": -87.60},
            "profile": "walk",
            "depart_at": "2026-04-07T08:00:00",
            "stops": [{"lat": 41.87, "lon": -87.65}],
            "stop_order_mode": "ordered",
            "blocked_segments": [
                {
                    "start": {"lat": 41.88, "lon": -87.63},
                    "end": {"lat": 41.881, "lon": -87.631},
                    "label": "Cấm thử nghiệm",
                    "buffer_m": 45,
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["totals"]["total_distance_m"] == 1200
    assert planner.calls[0]["kwargs"]["stops"] == [(41.87, -87.65)]
    assert planner.calls[0]["kwargs"]["stop_order_mode"] == "ordered"
    assert planner.calls[0]["kwargs"]["blocked_segments"][0]["label"] == "Cấm thử nghiệm"
