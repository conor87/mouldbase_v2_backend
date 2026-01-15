# routers/moulds_book.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime

from db.database import SessionLocal, db_dependency
from models.moulds_book import MouldsBook
from models.mould import Mould
from schemas.moulds_book import MouldsBookRead
from app.images import save_upload_file

router = APIRouter(prefix="/book", tags=["moulds_book"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_date_or_none(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid created date format. Use YYYY-MM-DD.",
            ) from exc


# -------------------------
# CREATE (POST /book/)
# -------------------------
@router.post("/", response_model=MouldsBookRead)
async def create_book_entry(
    mould_id: int = Form(...),
    sv: int = Form(0),
    tpm_type: int = Form(0),
    status: int = Form(0),
    created: Optional[str] = Form(None),
    opis_zgloszenia: Optional[str] = Form(None),
    ido: int = Form(0),
    czas_trwania: int = Form(0),
    czas_wylaczenia: int = Form(0),
    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),
    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    mould = db.query(Mould).filter(Mould.id == mould_id).first()
    if not mould:
        raise HTTPException(status_code=404, detail="Mould not found")

    photo1_url = None
    photo2_url = None

    if extra_photo_1 is not None:
        _, photo1_url = await save_upload_file(extra_photo_1, media_dir="media/book")
    elif extra_photo_1_path:
        photo1_url = extra_photo_1_path

    if extra_photo_2 is not None:
        _, photo2_url = await save_upload_file(extra_photo_2, media_dir="media/book")
    elif extra_photo_2_path:
        photo2_url = extra_photo_2_path

    created_date = parse_date_or_none(created)

    book = MouldsBook(
        mould_id=mould_id,
        sv=sv,
        tpm_type=tpm_type,
        status=status,
        opis_zgloszenia=opis_zgloszenia,
        ido=ido,
        czas_trwania=czas_trwania,
        czas_wylaczenia=czas_wylaczenia,
        extra_photo_1=photo1_url,
        extra_photo_2=photo2_url,
    )
    if created_date is not None:
        book.created = created_date

    db.add(book)
    db.commit()
    db.refresh(book)
    return book


# -------------------------
# READ LIST (GET /book/)
# -------------------------
@router.get("/", response_model=List[MouldsBookRead])
async def read_moulds_books(
    db: db_dependency,
    search: str | None = Query(None, description="Szukana forma (mould_number)"),
    skip: int = 0,
    limit: int = 1000,
):
    query = db.query(MouldsBook)

    if search:
        like = f"%{search}%"
        # relacja: MouldsBook.mould -> Mould
        query = query.filter(MouldsBook.mould.has(Mould.mould_number.ilike(like)))

    return query.offset(skip).limit(limit).all()


# -------------------------
# READ SINGLE (GET /book/{book_id})
# -------------------------
@router.get("/{book_id}", response_model=MouldsBookRead)
async def read_book_entry(
    book_id: int = Path(..., description="ID wpisu książki"),
    db: db_dependency = None,
):
    entry = db.query(MouldsBook).filter(MouldsBook.id == book_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Book entry not found")
    return entry


# -------------------------
# UPDATE (PUT /book/{book_id})
# -------------------------
@router.put("/{book_id}", response_model=MouldsBookRead)
async def update_book_entry(
    book_id: int = Path(..., description="ID wpisu książki"),

    sv: Optional[int] = Form(None),
    tpm_type: Optional[int] = Form(None),
    status: Optional[int] = Form(None),
    created: Optional[str] = Form(None),
    opis_zgloszenia: Optional[str] = Form(None),
    ido: Optional[int] = Form(None),
    czas_trwania: Optional[int] = Form(None),
    czas_wylaczenia: Optional[int] = Form(None),

    extra_photo_1: Optional[UploadFile] = File(None),
    extra_photo_1_path: Optional[str] = Form(None),

    extra_photo_2: Optional[UploadFile] = File(None),
    extra_photo_2_path: Optional[str] = Form(None),

    db: Session = Depends(get_db),
):
    entry = db.query(MouldsBook).filter(MouldsBook.id == book_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Book entry not found")

    # поля – aktualizuj tylko jeśli przyszły
    if sv is not None:
        entry.sv = sv
    if tpm_type is not None:
        entry.tpm_type = tpm_type
    if status is not None:
        entry.status = status
    if created is not None:
        created_date = parse_date_or_none(created)
        if created_date is not None:
            entry.created = created_date
    if opis_zgloszenia is not None:
        entry.opis_zgloszenia = opis_zgloszenia
    if ido is not None:
        entry.ido = ido
    if czas_trwania is not None:
        entry.czas_trwania = czas_trwania
    if czas_wylaczenia is not None:
        entry.czas_wylaczenia = czas_wylaczenia

    # zdjęcia: upload ma pierwszeństwo, potem path, inaczej zostaw
    if extra_photo_1 is not None:
        _, url = await save_upload_file(extra_photo_1, media_dir="media/book")
        entry.extra_photo_1 = url
    elif extra_photo_1_path is not None:
        entry.extra_photo_1 = extra_photo_1_path

    if extra_photo_2 is not None:
        _, url = await save_upload_file(extra_photo_2, media_dir="media/book")
        entry.extra_photo_2 = url
    elif extra_photo_2_path is not None:
        entry.extra_photo_2 = extra_photo_2_path

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# -------------------------
# DELETE (DELETE /book/{book_id})
# -------------------------
@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book_entry(
    book_id: int = Path(..., description="ID wpisu książki"),
    db: Session = Depends(get_db),
):
    entry = db.query(MouldsBook).filter(MouldsBook.id == book_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Book entry not found")

    db.delete(entry)
    db.commit()
    return
