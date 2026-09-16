from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.models import Coordinate, RouteContext, RouteResponse, RouteSegment, RouteSummary, RouteTotals


class FakeBoundary:
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
        return 41.6 <= lat <= 42.0 and -87.9 <= lon <= -87.5


class FakeRailAssets:
    lines = {"type": "FeatureCollection", "metadata": {"generated_at": "2026-04-07T00:00:00+00:00"}, "features": []}
    stations = []
    generated_at = "2026-04-07T00:00:00+00:00"


class FakeContextualFactors:
    generated_at = "2026-04-07T00:00:00+00:00"
    time_profiles = [{"id": "morning_peak", "label": "Cao điểm sáng"}]
    congestion_corridors = {"type": "FeatureCollection", "features": []}
    hazard_zones = {"type": "FeatureCollection", "features": []}


class FakePlanner:
    async def plan(self, origin, destination, profile, depart_at, **kwargs):
        raise ValueError("Cả hai điểm phải nằm trong ranh giới thành phố Chicago.")


class SuccessfulPlanner:
    def __init__(self):
        self.calls = []

    async def plan(self, origin, destination, profile, depart_at, **kwargs):
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


def test_boundary_meta_endpoint():
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
