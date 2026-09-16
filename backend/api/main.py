from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.config import Settings
from backend.api.models import AdvancedRouteRequest, BoundaryResponse, ContextMetaResponse, RailMetaResponse, RouteResponse
from backend.api.services.boundary import ChicagoBoundary
from backend.api.services.contextual_factors import ContextualFactorsStore
from backend.api.services.rail_assets import RailAssetStore
from backend.api.services.routing import RoutePlanner


def _parse_coordinate_pair(value: str) -> tuple[float, float]:
    try:
        lat_str, lon_str = [part.strip() for part in value.split(",", 1)]
        return float(lat_str), float(lon_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="Tọa độ phải đúng định dạng 'lat,lon'.")


def _parse_depart_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="depart_at phải là thời gian theo định dạng ISO-8601.") from exc


def create_app(
    settings: Settings | None = None,
    *,
    boundary: ChicagoBoundary | None = None,
    rail_assets: RailAssetStore | None = None,
    contextual_factors: ContextualFactorsStore | None = None,
    planner: RoutePlanner | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    boundary = boundary or ChicagoBoundary(settings.boundary_asset)
    rail_assets = rail_assets or RailAssetStore(
        settings.rail_lines_asset,
        settings.rail_stations_asset,
    )
    contextual_factors = contextual_factors or ContextualFactorsStore(
        settings.contextual_factors_asset,
        settings.chicago_timezone,
    )
    planner = planner or RoutePlanner(
        boundary=boundary,
        rail_assets=rail_assets,
        contextual_factors=contextual_factors,
        timezone_name=settings.chicago_timezone,
        candidate_limit=settings.candidate_limit,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(title="Bản đồ tìm đường Chicago", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.boundary = boundary
    app.state.rail_assets = rail_assets
    app.state.contextual_factors = contextual_factors
    app.state.planner = planner

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/meta/boundary", response_model=BoundaryResponse)
    async def get_boundary() -> BoundaryResponse:
        return BoundaryResponse(
            bbox=boundary.bbox,
            feature_collection=boundary.feature_collection,
            source=boundary.source,
            generated_at=boundary.generated_at,
        )

    @app.get("/api/meta/rail", response_model=RailMetaResponse)
    async def get_rail() -> RailMetaResponse:
        return RailMetaResponse(
            lines=rail_assets.lines,
            stations=rail_assets.stations,
            generated_at=rail_assets.generated_at,
        )

    @app.get("/api/meta/context", response_model=ContextMetaResponse)
    async def get_context() -> ContextMetaResponse:
        return ContextMetaResponse(
            time_profiles=contextual_factors.time_profiles,
            congestion_corridors=contextual_factors.congestion_corridors,
            hazard_zones=contextual_factors.hazard_zones,
            generated_at=contextual_factors.generated_at,
        )

    @app.get("/api/route", response_model=RouteResponse)
    async def get_route(
        from_: str = Query(..., alias="from"),
        to_: str = Query(..., alias="to"),
        profile: str = Query("walk", pattern="^walk$"),
        depart_at: str | None = Query(None),
    ) -> RouteResponse:
        origin = _parse_coordinate_pair(from_)
        destination = _parse_coordinate_pair(to_)
        depart_time = _parse_depart_at(depart_at)

        try:
            return await planner.plan(origin, destination, profile, depart_time)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503,
                detail="Hệ thống tính đường tạm thời chưa sẵn sàng.",
            ) from exc

    @app.post("/api/route", response_model=RouteResponse)
    async def post_route(request: AdvancedRouteRequest) -> RouteResponse:
        origin = (request.origin.lat, request.origin.lon)
        destination = (request.destination.lat, request.destination.lon)
        stops = [(stop.lat, stop.lon) for stop in request.stops]
        blocked_segments = [
            {
                "start": {"lat": item.start.lat, "lon": item.start.lon},
                "end": {"lat": item.end.lat, "lon": item.end.lon},
                "label": item.label,
                "buffer_m": item.buffer_m,
            }
            for item in request.blocked_segments
        ]
        try:
            return await planner.plan(
                origin,
                destination,
                request.profile,
                request.depart_at,
                stops=stops,
                stop_order_mode=request.stop_order_mode,
                blocked_segments=blocked_segments,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503,
                detail="Hệ thống tính đường tạm thời chưa sẵn sàng.",
            ) from exc

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse("frontend/index.html")

    app.mount("/static", StaticFiles(directory="frontend"), name="static")
    return app


app = create_app()
