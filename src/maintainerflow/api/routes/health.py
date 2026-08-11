from fastapi import APIRouter
from fastapi.responses import JSONResponse

from maintainerflow.api.dependencies import DatabaseDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def readiness(database: DatabaseDep) -> dict[str, str] | JSONResponse:
    if await database.ping():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "unavailable"})
