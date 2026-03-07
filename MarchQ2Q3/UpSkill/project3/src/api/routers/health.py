from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}
