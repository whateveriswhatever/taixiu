from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbDep

router = APIRouter()


@router.get("/health", summary="Kiểm tra trạng thái hoạt động của Service")
async def health_check() -> dict:
    return {"status": "ok", "service": "game-service"}


@router.get("/ready", summary="Kiểm tra kết nối Database")
async def ready_check(db: DbDep) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}

