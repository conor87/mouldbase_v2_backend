# routers/changeovers.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import SessionLocal, db_dependency
from models.changeovers import Changeover
from models.changeovers_log import ChangeoverLog
from models.mould import Mould
from schemas.changeovers import ChangeoverRead

# auth
from routers.auth import user_dependency, admin_required

router = APIRouter(prefix="/changeovers", tags=["changeovers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- helpers ----------

def parse_dt_or_none(val: Optional[str], field_name: str) -> Optional[datetime]:
    """
    Obsługa datetime-local z React: 'YYYY-MM-DDTHH:MM'
    plus tolerancja dla: 'YYYY-MM-DD HH:MM', pełny ISO z sekundami.
    Puste stringi -> None.
    """
    if val is None:
        return None
    s = val.strip()
    if s == "":
        return None

    # typowe z datetime-local: 2025-12-30T14:05
    try:
        # fromisoformat akceptuje: YYYY-MM-DDTHH:MM[:SS[.ffffff]][+HH:MM]
        # nie akceptuje 'Z' -> zamień na +00:00
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2)
    except ValueError:
        pass

    # fallback: "YYYY-MM-DD HH:MM"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    raise HTTPException(status_code=400, detail=f"Invalid datetime format for '{field_name}' (use YYYY-MM-DDTHH:MM)")


def dump_changeover(co: Changeover) -> dict:
    return {
        "id": co.id,
        "from_mould_id": co.from_mould_id,
        "to_mould_id": co.to_mould_id,
        "available_date": co.available_date.isoformat() if co.available_date else None,
        "needed_date": co.needed_date.isoformat() if co.needed_date else None,
        "czy_wykonano": bool(co.czy_wykonano),
        "updated_by": co.updated_by,
        "created": co.created.isoformat() if co.created else None,
        "updated": co.updated.isoformat() if co.updated else None,
    }


def add_log(
    db: Session,
    *,
    changeover_id: int,
    action: str,
    old_data: Optional[dict],
    new_data: Optional[dict],
    updated_by: Optional[str],
):
    """
    Wymaga modelu ChangeoverLog z polami:
    changeover_id, action, old_data(JSONB), new_data(JSONB), updated_by, created(DateTime)
    """
    log = ChangeoverLog(
        changeover_id=changeover_id,
        action=action,
        old_data=old_data,
        new_data=new_data,
        updated_by=updated_by,
    )
    db.add(log)


def require_mould(db: Session, mould_id: int, field_name: str):
    m = db.query(Mould).filter(Mould.id == mould_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"{field_name} not found")
    return m


def get_username_from_user(user: Optional[dict]) -> Optional[str]:
    if not user:
        return None
    # zależnie jak zwracasz w get_current_user
    return user.get("username") or user.get("sub") or user.get("name")


# ---------- routes ----------

@router.post("/", response_model=ChangeoverRead, dependencies=[Depends(admin_required)])
async def create_changeover(
    from_mould_id: int = Form(...),
    to_mould_id: int = Form(...),
    available_date: Optional[str] = Form(None),
    needed_date: Optional[str] = Form(None),
    czy_wykonano: bool = Form(False),

    db: Session = Depends(get_db),
    user: user_dependency = None,  # NIE dawaj Depends() – user_dependency już ma Depends w Annotated
):
    require_mould(db, from_mould_id, "from_mould")
    require_mould(db, to_mould_id, "to_mould")

    av = parse_dt_or_none(available_date, "available_date")
    nd = parse_dt_or_none(needed_date, "needed_date")

    username = get_username_from_user(user)

    co = Changeover(
        from_mould_id=from_mould_id,
        to_mould_id=to_mould_id,
        available_date=av,
        needed_date=nd,
        czy_wykonano=bool(czy_wykonano),
        updated_by=username,
    )

    db.add(co)
    db.commit()
    db.refresh(co)

    # log CREATE
    add_log(
        db,
        changeover_id=co.id,
        action="CREATE",
        old_data=None,
        new_data=dump_changeover(co),
        updated_by=username,
    )
    db.commit()

    db.refresh(co)
    return co


@router.get("/", response_model=List[ChangeoverRead])
async def list_changeovers(
    db: db_dependency,
    # kompatybilność
    skip: int = 0,
    limit: int = 5000,

    only_open: bool = Query(False, description="Tylko niewykonane"),

    # ✅ nowa logika wyświetlania:
    done_page: int = Query(1, ge=1, description="Strona zrealizowanych"),
    done_page_size: int = Query(10, ge=1, le=200, description="Ile zrealizowanych na stronę"),
):
    """
    Zwraca:
    - najpierw WSZYSTKIE niewykonane (czy_wykonano = false)
    - potem zrealizowane (czy_wykonano = true) stronicowane po 10 (done_page_size)
    """
    q_open = db.query(Changeover).filter(Changeover.czy_wykonano == False)  # noqa: E712
    open_rows = q_open.order_by(Changeover.id.desc()).all()

    if only_open:
        # opcjonalnie zostawiamy skip/limit dla kompatybilności
        if skip or limit:
            return open_rows[skip: skip + limit]
        return open_rows

    q_done = db.query(Changeover).filter(Changeover.czy_wykonano == True)  # noqa: E712
    done_skip = (done_page - 1) * done_page_size
    done_rows = q_done.order_by(Changeover.id.desc()).offset(done_skip).limit(done_page_size).all()

    # kompatybilność: jeśli ktoś nadal używa skip/limit na całości
    rows = open_rows + done_rows
    if skip or limit:
        return rows[skip: skip + limit]
    return rows


@router.get("/{changeover_id}", response_model=ChangeoverRead)
async def get_changeover(changeover_id: int, db: db_dependency):
    co = db.query(Changeover).filter(Changeover.id == changeover_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Changeover not found")
    return co


@router.put("/{changeover_id}", response_model=ChangeoverRead, dependencies=[Depends(admin_required)])
async def update_changeover(
    changeover_id: int,

    from_mould_id: Optional[int] = Form(None),
    to_mould_id: Optional[int] = Form(None),
    available_date: Optional[str] = Form(None),  # "" -> None
    needed_date: Optional[str] = Form(None),     # "" -> None
    czy_wykonano: Optional[bool] = Form(None),

    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    co = db.query(Changeover).filter(Changeover.id == changeover_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Changeover not found")

    username = get_username_from_user(user)
    old_snapshot = dump_changeover(co)

    if from_mould_id is not None:
        require_mould(db, from_mould_id, "from_mould")
        co.from_mould_id = from_mould_id

    if to_mould_id is not None:
        require_mould(db, to_mould_id, "to_mould")
        co.to_mould_id = to_mould_id

    if available_date is not None:
        co.available_date = parse_dt_or_none(available_date, "available_date")

    if needed_date is not None:
        co.needed_date = parse_dt_or_none(needed_date, "needed_date")

    if czy_wykonano is not None:
        co.czy_wykonano = bool(czy_wykonano)

    co.updated_by = username

    db.add(co)
    db.commit()
    db.refresh(co)

    # log UPDATE / TOGGLE_DONE (opcjonalnie rozróżnienie)
    new_snapshot = dump_changeover(co)
    action = "TOGGLE_DONE" if (czy_wykonano is not None and old_snapshot.get("czy_wykonano") != new_snapshot.get("czy_wykonano")) else "UPDATE"

    add_log(
        db,
        changeover_id=co.id,
        action=action,
        old_data=old_snapshot,
        new_data=new_snapshot,
        updated_by=username,
    )
    db.commit()

    db.refresh(co)
    return co


@router.delete("/{changeover_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_changeover(
    changeover_id: int,
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    """
    Uwaga:
    - jeśli ChangeoverLog ma FK z ondelete=CASCADE, logi skasują się razem z rekordem.
      Jeśli chcesz zachować historię po usunięciu – w DB ustaw FK logów bez CASCADE
      albo wprowadź soft-delete (np. kolumna visible).
    """
    co = db.query(Changeover).filter(Changeover.id == changeover_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Changeover not found")

    username = get_username_from_user(user)
    old_snapshot = dump_changeover(co)

    # log DELETE (przed usunięciem)
    add_log(
        db,
        changeover_id=co.id,
        action="DELETE",
        old_data=old_snapshot,
        new_data=None,
        updated_by=username,
    )
    db.commit()

    db.delete(co)
    db.commit()
    return
