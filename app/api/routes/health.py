from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: DbSession):
    await db.execute(text("SELECT 1"))
    return {"database": "ok"}
