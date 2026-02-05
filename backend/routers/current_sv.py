from typing import Any, Dict, List

from fastapi import APIRouter
from sqlalchemy import text

from db.database import db_dependency

router = APIRouter(prefix="/current_sv", tags=["current_sv"])


@router.get("/", response_model=List[Dict[str, Any]])
async def list_current_sv(
    db: db_dependency,
    skip: int = 0,
    limit: int = 1000,
):
    rows = (
        db.execute(
            text("SELECT * FROM current_sv OFFSET :skip LIMIT :limit"),
            {"skip": skip, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
