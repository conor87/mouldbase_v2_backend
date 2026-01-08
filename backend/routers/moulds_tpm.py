# routers/moulds_tpm.py - fragment create_tpm
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from db.database import SessionLocal
from models.moulds_tpm import MouldsTpm
from models.mould import Mould
from schemas.moulds_tpm import MouldsTpmRead
from app.images import save_upload_file
from db.database import db_dependency
from sqlalchemy import or_

router = APIRouter(prefix="/tpm", tags=["moulds_tpm"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=MouldsTpmRead)
async def create_tpm(
    mould_id: int = Form(...),
    sv: int = Form(0),
    tpm_time_type: int = Form(0),
    opis_zgloszenia: str = Form(None),
    ido: int = Form(0),
    status: int = Form(0),
    changed: str = Form("1900-01-01"),
    author: str = Form(None),
    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),
    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    mould = db.query(Mould).filter(Mould.id == mould_id).first()
    if not mould:
        raise HTTPException(status_code=404, detail="Mould not found")

    changed_date = None
    if changed:
        changed_date = datetime.strptime(changed, "%Y-%m-%d").date()

    photo1_url = None
    photo2_url = None
    if extra_photo_1 is not None:
        _, photo1_url = await save_upload_file(extra_photo_1, media_dir="media/tpm")
    elif extra_photo_1_path:
        photo1_url = extra_photo_1_path

    if extra_photo_2 is not None:
        _, photo2_url = await save_upload_file(extra_photo_2, media_dir="media/tpm")
    elif extra_photo_2_path:
        photo2_url = extra_photo_2_path

    tpm = MouldsTpm(
        mould_id=mould_id,
        sv=sv,
        tpm_time_type=tpm_time_type,
        opis_zgloszenia=opis_zgloszenia,
        ido=ido,
        status=status,
        changed=changed_date,
        author=author,
        extra_photo_1=photo1_url,
        extra_photo_2=photo2_url,
    )
    db.add(tpm)
    db.commit()
    db.refresh(tpm)
    return tpm

# @router.get("/", response_model=List[MouldsTpmRead])
# #async def read_companys(db: db_dependency, skip: int = 0, limit: int = 100, user=Depends(get_current_user)):
# async def read_molds_tpms(db: db_dependency, skip: int = 0, limit: int = 100):
#     molds_tpms = db.query(MouldsTpm).offset(skip).limit(limit).all()
#     return molds_tpms


@router.get("/", response_model=List[MouldsTpmRead])
async def read_molds_tpms(
    db: db_dependency,
    search: str | None = Query(None, description="Szukana forma"),
    skip: int = 0,
    limit: int = 1000,
):
    query = db.query(MouldsTpm)

    if search:
        like = f"%{search}%"
        query = query.filter(
            MouldsTpm.mould.has(Mould.mould_number.ilike(like))
        )

    molds = query.offset(skip).limit(limit).all()
    return molds

@router.get("/{tpm_id}", response_model=MouldsTpmRead)
async def read_tpm_one(
    tpm_id: int,
    db: Session = Depends(get_db),
):
    tpm = db.query(MouldsTpm).filter(MouldsTpm.id == tpm_id).first()
    if not tpm:
        raise HTTPException(status_code=404, detail="TPM entry not found")
    return tpm

@router.put("/{tpm_id}", response_model=MouldsTpmRead)
async def update_tpm(
    tpm_id: int,

    sv: Optional[int] = Form(None),
    tpm_time_type: Optional[int] = Form(None),
    opis_zgloszenia: Optional[str] = Form(None),
    ido: Optional[int] = Form(None),
    status: Optional[int] = Form(None),
    changed: Optional[str] = Form(None),
    author: Optional[str] = Form(None),

    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),
    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),

    db: Session = Depends(get_db),
):
    tpm = db.query(MouldsTpm).filter(MouldsTpm.id == tpm_id).first()
    if not tpm:
        raise HTTPException(status_code=404, detail="TPM entry not found")

    # --- pola proste (partial update) ---
    if sv is not None:
        tpm.sv = sv
    if tpm_time_type is not None:
        tpm.tpm_time_type = tpm_time_type
    if opis_zgloszenia is not None:
        tpm.opis_zgloszenia = opis_zgloszenia
    if ido is not None:
        tpm.ido = ido
    if status is not None:
        tpm.status = status
    if author is not None:
        tpm.author = author

    # --- changed jako data ---
    if changed is not None:
        val = changed.strip()
        if val == "":
            tpm.changed = None
        else:
            try:
                tpm.changed = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format for 'changed' (expected YYYY-MM-DD)"
                )

    # --- zdjęcia ---
    # jeśli upload -> zapis, jeśli path -> ustaw/wyczyść, jeśli brak -> nie ruszaj

    if extra_photo_1 is not None:
        _, url1 = await save_upload_file(extra_photo_1, media_dir="media/tpm")
        tpm.extra_photo_1 = url1
    elif extra_photo_1_path is not None:
        tpm.extra_photo_1 = extra_photo_1_path.strip() or None

    if extra_photo_2 is not None:
        _, url2 = await save_upload_file(extra_photo_2, media_dir="media/tpm")
        tpm.extra_photo_2 = url2
    elif extra_photo_2_path is not None:
        tpm.extra_photo_2 = extra_photo_2_path.strip() or None

    db.add(tpm)
    db.commit()
    db.refresh(tpm)
    return tpm

@router.delete("/{tpm_id}", status_code=204)
async def delete_tpm(
    tpm_id: int,
    db: Session = Depends(get_db),
):
    tpm = db.query(MouldsTpm).filter(MouldsTpm.id == tpm_id).first()
    if not tpm:
        raise HTTPException(status_code=404, detail="TPM entry not found")

    db.delete(tpm)
    db.commit()
    return
