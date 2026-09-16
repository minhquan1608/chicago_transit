from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

from backend.api.services.routing import RoutePlanner


TZ = ZoneInfo("America/Chicago")


class FakeBoundary:
    generated_at = "2026-04-07T00:00:00+00:00"

    def contains(self, lat: float, lon: float) -> bool:
        return 41.6 <= lat <= 42.1 and -87.9 <= lon <= -87.5


class FakeRailAssets:
    generated_at = "2026-04-07T00:00:00+00:00"
    line_colors = {"Red": "#C60C30", "Blue": "#00A1DE"}
    
    def resolve_station(self, stop_name: str, line_id: str | None = None):
        if stop_name == "Howard":
            return {"stop_id": "40900", "stop_name": "Howard", "routes": ["Red"]}
        return None
        


def build_planner() -> RoutePlanner:
    return RoutePlanner(
        boundary=FakeBoundary(),
        rail_assets=FakeRailAssets(),
        timezone_name="America/Chicago",
        candidate_limit=3,
    )


def test_outside_city_points_raise_value_error():
    planner = build_planner()
    try:
        asyncio.run(planner.plan((42.4, -87.63), (41.79, -87.6), "walk", datetime(2026, 4, 7, 8, 0, tzinfo=TZ)))
    except ValueError as exc:
        assert "ranh giới thành phố Chicago" in str(exc)
    else:
        raise AssertionError("Expected ValueError for outside-city point.")


def test_valid_route_returns_response():
    planner = build_planner()
    fake_json = {
        "total_time": 600,
        "total_distance": 1200,
        "path": [
            {"lat": 41.88, "lon": -87.63, "type": 0},
            {"lat": 41.89, "lon": -87.62, "type": 0}
        ]
    }
    mock_run = MagicMock()
    mock_run.stdout = json.dumps(fake_json)
    
    with patch("subprocess.run", return_value=mock_run):
        result = asyncio.run(planner.plan(
            (41.88, -87.63), 
            (41.89, -87.62), 
            "walk", 
            datetime(2026, 4, 7, 8, 0, tzinfo=TZ)
        ))
        
    assert result.totals.total_sec == 600
    assert result.totals.total_distance_m > 1000
    assert len(result.segments) > 0
    assert result.segments[0].kind == "walk"
