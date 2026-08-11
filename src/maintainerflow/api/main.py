import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from maintainerflow.api.routes.github_webhooks import router as github_router
from maintainerflow.api.routes.health import router as health_router
from maintainerflow.config import Settings, get_settings
from maintainerflow.persistence.database import Database


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        active_settings = settings or get_settings()
        logging.basicConfig(
            level=active_settings.log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        app.state.settings = active_settings
        app.state.database = Database(active_settings.database_url)
        yield
        await app.state.database.dispose()

    application = FastAPI(title="MaintainerFlow", version="0.1.0", lifespan=lifespan)
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router)
    application.include_router(github_router)

    return application


app = create_app()
