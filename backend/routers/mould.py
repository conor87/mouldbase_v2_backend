# routers/mould.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Path, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Optional, Dict, List

from db.database import SessionLocal, db_dependency
from models.mould import Mould
from schemas.mould import MouldReadWithTpm
from app.images import save_upload_file
from sqlalchemy import or_, and_, exists

from routers.auth import admin_required, user_dependency 

# ✅ TPM
from models.moulds_tpm import MouldsTpm, Statusy

router = APIRouter(prefix="/moulds", tags=["moulds"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# CREATE
# =========================
@router.post("/", response_model=MouldReadWithTpm, dependencies=[Depends(admin_required)])
async def create_mould(
    mould_number: str = Form(...),
    product: str = Form(""),
    released: Optional[str] = Form("1900-01-01"),
    company: str = Form("Lamela"),
    czy_przezbrajalna: bool = Form(False),
    num_of_cavities: Optional[str] = Form(None),
    tool_weight: Optional[str] = Form(None),
    total_cycles: int = Form(0),
    to_maint_cycles: int = Form(0),
    from_maint_cycles: int = Form(0),
    place: int = Form(0),
    status: int = Form(0),
    notes: Optional[str] = Form(None),

    mould_photo: Optional[UploadFile] = File(None),
    mould_photo_path: Optional[str] = Form(None),

    product_photo: Optional[UploadFile] = File(None),
    product_photo_path: Optional[str] = Form(None),

    hot_system_photo: Optional[UploadFile] = File(None),
    hot_system_photo_path: Optional[str] = Form(None),

    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),

    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),

    extra_photo_3: Optional[UploadFile] = File(None),
    extra_photo_3_path: Optional[str] = Form(None),

    extra_photo_4: Optional[UploadFile] = File(None),
    extra_photo_4_path: Optional[str] = Form(None),

    extra_photo_5: Optional[UploadFile] = File(None),
    extra_photo_5_path: Optional[str] = Form(None),

    db: Session = Depends(get_db),
):
    mould_number_up = mould_number.strip().upper()

    released_date = None
    if released and released.strip():
        released_date = datetime.strptime(released, "%Y-%m-%d").date()

    existing = db.query(Mould).filter(Mould.mould_number == mould_number_up).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mould with this number already exists")

    file_map = {
        "mould_photo": (mould_photo, mould_photo_path),
        "product_photo": (product_photo, product_photo_path),
        "hot_system_photo": (hot_system_photo, hot_system_photo_path),
        "extra_photo_1": (extra_photo_1, extra_photo_1_path),
        "extra_photo_2": (extra_photo_2, extra_photo_2_path),
        "extra_photo_3": (extra_photo_3, extra_photo_3_path),
        "extra_photo_4": (extra_photo_4, extra_photo_4_path),
        "extra_photo_5": (extra_photo_5, extra_photo_5_path),
    }

    saved_urls: Dict[str, Optional[str]] = {}
    for field_name, (upload_obj, path_value) in file_map.items():
        if upload_obj is not None:
            _, public_url = await save_upload_file(upload_obj)
            saved_urls[field_name] = public_url
        elif path_value:
            saved_urls[field_name] = path_value
        else:
            saved_urls[field_name] = None

    m = Mould(
        mould_number=mould_number_up,
        product=product,
        released=released_date,
        company=company,
        czy_przezbrajalna=czy_przezbrajalna,
        num_of_cavities=num_of_cavities,
        notes=notes,
        tool_weight=tool_weight,
        total_cycles=total_cycles,
        to_maint_cycles=to_maint_cycles,
        from_maint_cycles=from_maint_cycles,
        place=place,
        status=status,
        mould_photo=saved_urls.get("mould_photo"),
        product_photo=saved_urls.get("product_photo"),
        hot_system_photo=saved_urls.get("hot_system_photo"),
        extra_photo_1=saved_urls.get("extra_photo_1"),
        extra_photo_2=saved_urls.get("extra_photo_2"),
        extra_photo_3=saved_urls.get("extra_photo_3"),
        extra_photo_4=saved_urls.get("extra_photo_4"),
        extra_photo_5=saved_urls.get("extra_photo_5"),
    )

    db.add(m)
    db.commit()
    db.refresh(m)

    out = MouldReadWithTpm.model_validate(m).model_dump()
    out["has_open_tpm"] = False
    return out


# =========================
# LIST
# =========================
@router.get("/", response_model=List[MouldReadWithTpm])
async def read_molds(
    db: db_dependency,
    search: str | None = Query(None, description="Szukane słowo w mould_number lub product"),
    skip: int = 0,
    limit: int = 1000,
):
    open_statuses = [Statusy.OTWARTY.value, Statusy.W_TRAKCIE_REALIZACJI.value]

    has_open_tpm_expr = exists().where(
        and_(
            MouldsTpm.mould_id == Mould.id,
            MouldsTpm.status.in_(open_statuses),
        )
    ).label("has_open_tpm")

    query = db.query(Mould, has_open_tpm_expr)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Mould.mould_number.ilike(like), Mould.product.ilike(like)))

    rows = query.offset(skip).limit(limit).all()

    result = []
    for mould, has_open_tpm in rows:
        data = MouldReadWithTpm.model_validate(mould).model_dump()
        data["has_open_tpm"] = bool(has_open_tpm)
        result.append(data)

    return result


# =========================
# GET ONE
# =========================
@router.get("/{mould_number}", response_model=MouldReadWithTpm)
async def get_mould(mould_number: str, db: db_dependency):
    mould_number_up = mould_number.strip().upper()

    m = db.query(Mould).filter(Mould.mould_number == mould_number_up).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mould not found")

    open_statuses = [Statusy.OTWARTY.value, Statusy.W_TRAKCIE_REALIZACJI.value]
    has_open = (
        db.query(MouldsTpm.id)
        .filter(and_(MouldsTpm.mould_id == m.id, MouldsTpm.status.in_(open_statuses)))
        .first()
        is not None
    )

    out = MouldReadWithTpm.model_validate(m).model_dump()
    out["has_open_tpm"] = bool(has_open)
    return out


# =========================
# UPDATE  ✅ PUT /moulds/{mould_number}
# =========================
@router.put("/{mould_number}", response_model=MouldReadWithTpm, dependencies=[Depends(admin_required)])
async def update_mould(
    mould_number: str = Path(...),

    new_mould_number: Optional[str] = Form(None),
    product: Optional[str] = Form(None),
    released: Optional[str] = Form(None),
    company: Optional[str] = Form(None),
    czy_przezbrajalna: Optional[bool] = Form(None),
    num_of_cavities: Optional[str] = Form(None),
    tool_weight: Optional[str] = Form(None),
    total_cycles: Optional[int] = Form(None),
    to_maint_cycles: Optional[int] = Form(None),
    from_maint_cycles: Optional[int] = Form(None),
    place: Optional[int] = Form(None),
    status: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),

    mould_photo: Optional[UploadFile] = File(None),
    mould_photo_path: Optional[str] = Form(None),

    product_photo: Optional[UploadFile] = File(None),
    product_photo_path: Optional[str] = Form(None),

    hot_system_photo: Optional[UploadFile] = File(None),
    hot_system_photo_path: Optional[str] = Form(None),

    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),

    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),

    extra_photo_3: Optional[UploadFile] = File(None),
    extra_photo_3_path: Optional[str] = Form(None),

    extra_photo_4: Optional[UploadFile] = File(None),
    extra_photo_4_path: Optional[str] = Form(None),

    extra_photo_5: Optional[UploadFile] = File(None),
    extra_photo_5_path: Optional[str] = Form(None),

    db: Session = Depends(get_db),
):
    mould_number_up = mould_number.strip().upper()

    m: Mould | None = db.query(Mould).filter(Mould.mould_number == mould_number_up).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mould not found")

    if new_mould_number is not None:
        new_up = new_mould_number.strip().upper()
        if new_up != mould_number_up:
            exists_m = db.query(Mould).filter(Mould.mould_number == new_up).first()
            if exists_m:
                raise HTTPException(status_code=400, detail="Mould with this number already exists")
            m.mould_number = new_up

    if product is not None:
        m.product = product
    if company is not None:
        m.company = company
    if czy_przezbrajalna is not None:
        m.czy_przezbrajalna = czy_przezbrajalna
    if num_of_cavities is not None:
        m.num_of_cavities = num_of_cavities
    if tool_weight is not None:
        m.tool_weight = tool_weight
    if total_cycles is not None:
        m.total_cycles = total_cycles
    if to_maint_cycles is not None:
        m.to_maint_cycles = to_maint_cycles
    if from_maint_cycles is not None:
        m.from_maint_cycles = from_maint_cycles
    if place is not None:
        m.place = place
    if status is not None:
        m.status = status
    if notes is not None:
        m.notes = notes

    if released is not None:
        if released.strip() == "":
            m.released = None
        else:
            try:
                m.released = datetime.strptime(released, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid released date format. Use YYYY-MM-DD")

    file_map = {
        "mould_photo": (mould_photo, mould_photo_path),
        "product_photo": (product_photo, product_photo_path),
        "hot_system_photo": (hot_system_photo, hot_system_photo_path),
        "extra_photo_1": (extra_photo_1, extra_photo_1_path),
        "extra_photo_2": (extra_photo_2, extra_photo_2_path),
        "extra_photo_3": (extra_photo_3, extra_photo_3_path),
        "extra_photo_4": (extra_photo_4, extra_photo_4_path),
        "extra_photo_5": (extra_photo_5, extra_photo_5_path),
    }

    for field_name, (upload_obj, path_value) in file_map.items():
        if upload_obj is not None:
            _, public_url = await save_upload_file(upload_obj)
            setattr(m, field_name, public_url)
        elif path_value is not None:
            setattr(m, field_name, path_value if path_value.strip() != "" else None)

    db.commit()
    db.refresh(m)

    open_statuses = [Statusy.OTWARTY.value, Statusy.W_TRAKCIE_REALIZACJI.value]
    has_open = (
        db.query(MouldsTpm.id)
        .filter(and_(MouldsTpm.mould_id == m.id, MouldsTpm.status.in_(open_statuses)))
        .first()
        is not None
    )

    out = MouldReadWithTpm.model_validate(m).model_dump()
    out["has_open_tpm"] = bool(has_open)
    return out

@router.delete(
    "/{mould_number}",
    status_code=204,
    dependencies=[Depends(admin_required)],  # ✅ admin/superadmin przechodzi, ale niżej dopiero superadmin
)
async def delete_mould(
    mould_number: str = Path(...),
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    # ✅ tylko superadmin
    if not user or user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    mould_number_up = mould_number.strip().upper()

    m = db.query(Mould).filter(Mould.mould_number == mould_number_up).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mould not found")

    try:
        db.delete(m)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Nie można usunąć formy (powiązane rekordy / ograniczenia FK). Usuń zależności lub dodaj cascade/ondelete.",
        )

    return Response(status_code=204)
