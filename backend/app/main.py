from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.explain import router as explain_router
from app.runtime import RuntimeStatus, readiness_status
from app.search_api import router as search_router
from app.settings import get_settings


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class DependencyStatusResponse(BaseModel):
    name: str
    status: str
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    service: str
    environment: str
    dependencies: list[DependencyStatusResponse]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            environment=settings.environment,
        )

    @app.get("/ready", response_model=ReadinessResponse)
    async def ready() -> ReadinessResponse:
        dependencies = readiness_status(settings)
        return ReadinessResponse(
            status=_readiness_status(dependencies),
            service=settings.app_name,
            environment=settings.environment,
            dependencies=[
                DependencyStatusResponse(
                    name=dependency.name,
                    status=dependency.status,
                    detail=dependency.detail,
                )
                for dependency in dependencies
            ],
        )

    app.include_router(explain_router)
    app.include_router(search_router)

    return app


app = create_app()


def _readiness_status(dependencies: list[RuntimeStatus]) -> str:
    if any(dependency.status == "unavailable" for dependency in dependencies):
        return "unavailable"
    if any(dependency.status == "degraded" for dependency in dependencies):
        return "degraded"
    return "ok"
