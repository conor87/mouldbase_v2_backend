from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request, Query, status

from app.images import save_upload_file
from db.database import db_dependency
from models.service_guide import ServiceGuide, ServiceGuideStep
from schemas.service_guide import (
    ServiceGuideCreate,
    ServiceGuideRead,
    ServiceGuideStepCreate,
    ServiceGuideStepRead,
    ServiceGuideStepUpdate,
    ServiceGuideUpdate,
)

router = APIRouter(prefix="/service-guides", tags=["service_guides"])


def get_guide_or_404(db, guide_id: int) -> ServiceGuide:
    guide = db.query(ServiceGuide).filter(ServiceGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Service guide not found")
    return guide


def get_step_or_404(db, guide_id: int, step_id: int) -> ServiceGuideStep:
    step = (
        db.query(ServiceGuideStep)
        .filter(ServiceGuideStep.guide_id == guide_id, ServiceGuideStep.id == step_id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Service guide step not found")
    return step


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "tak", "on"}


def form_text(form, key: str, default=None):
    value = form.get(key)
    if hasattr(value, "filename"):
        return default
    if value is None:
        return default
    return str(value)


def form_int(form, key: str, default: int = 1) -> int:
    value = form_text(form, key, None)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@router.get("/", response_model=List[ServiceGuideRead])
async def list_service_guides(
    db: db_dependency,
    search: str | None = Query(None),
    mould_id: int | None = Query(None),
    skip: int = 0,
    limit: int = 1000,
):
    query = db.query(ServiceGuide)
    if mould_id is not None:
        query = query.filter(ServiceGuide.mould_id == mould_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (ServiceGuide.guide_number.ilike(like))
            | (ServiceGuide.product_name.ilike(like))
            | (ServiceGuide.review_reason.ilike(like))
        )
    return query.order_by(ServiceGuide.created_at.desc(), ServiceGuide.id.desc()).offset(skip).limit(limit).all()


@router.post("/", response_model=ServiceGuideRead, status_code=status.HTTP_201_CREATED)
async def create_service_guide(payload: ServiceGuideCreate, db: db_dependency):
    guide = ServiceGuide(**payload.model_dump())
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.get("/{guide_id}", response_model=ServiceGuideRead)
async def read_service_guide(guide_id: int, db: db_dependency):
    return get_guide_or_404(db, guide_id)


@router.put("/{guide_id}", response_model=ServiceGuideRead)
async def update_service_guide(guide_id: int, payload: ServiceGuideUpdate, db: db_dependency):
    guide = get_guide_or_404(db, guide_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(guide, key, value)
    guide.updated_at = datetime.utcnow()
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.put("/{guide_id}/complete", response_model=ServiceGuideRead)
async def complete_service_guide(guide_id: int, db: db_dependency):
    guide = get_guide_or_404(db, guide_id)
    if not guide.steps:
        raise HTTPException(
            status_code=400,
            detail="Nie mozna zaakceptowac przewodnika bez czynnosci.",
        )
    unfinished_steps = [step for step in guide.steps if not step.is_done]
    if unfinished_steps:
        raise HTTPException(
            status_code=400,
            detail="Nie mozna zaakceptowac przewodnika. Najpierw zaakceptuj wszystkie czynnosci.",
        )
    guide.status = "done"
    guide.completed_at = datetime.utcnow()
    guide.updated_at = datetime.utcnow()
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.put("/{guide_id}/reopen", response_model=ServiceGuideRead)
async def reopen_service_guide(guide_id: int, db: db_dependency):
    guide = get_guide_or_404(db, guide_id)
    guide.status = "open"
    guide.completed_at = None
    guide.updated_at = datetime.utcnow()
    for step in guide.steps:
        step.is_done = False
        step.performed_by = None
        step.updated_at = datetime.utcnow()
        db.add(step)
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.delete("/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_guide(guide_id: int, db: db_dependency):
    guide = get_guide_or_404(db, guide_id)
    db.delete(guide)
    db.commit()
    return


@router.post("/{guide_id}/steps", response_model=ServiceGuideStepRead, status_code=status.HTTP_201_CREATED)
async def create_service_guide_step(guide_id: int, request: Request, db: db_dependency):
    get_guide_or_404(db, guide_id)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        data = {
            "lp": form_int(form, "lp", 1),
            "fault": form_text(form, "fault", None),
            "confirmed_by": form_text(form, "confirmed_by", None),
            "repair": form_text(form, "repair", None),
            "performed_by": form_text(form, "performed_by", None),
            "is_done": parse_bool(form_text(form, "is_done", None), False),
        }

        photo_1 = form.get("extra_photo_1")
        if hasattr(photo_1, "filename") and photo_1.filename:
            _, data["extra_photo_1"] = await save_upload_file(photo_1, media_dir="media/service_guides")

        photo_2 = form.get("extra_photo_2")
        if hasattr(photo_2, "filename") and photo_2.filename:
            _, data["extra_photo_2"] = await save_upload_file(photo_2, media_dir="media/service_guides")
    else:
        payload = ServiceGuideStepCreate.model_validate(await request.json())
        data = payload.model_dump()

    step = ServiceGuideStep(guide_id=guide_id, **data)
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.put("/{guide_id}/steps/{step_id}", response_model=ServiceGuideStepRead)
async def update_service_guide_step(
    guide_id: int,
    step_id: int,
    request: Request,
    db: db_dependency,
):
    step = get_step_or_404(db, guide_id, step_id)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        if "lp" in form:
            step.lp = form_int(form, "lp", step.lp)
        if "fault" in form:
            step.fault = form_text(form, "fault", step.fault)
        if "confirmed_by" in form:
            step.confirmed_by = form_text(form, "confirmed_by", step.confirmed_by)
        if "repair" in form:
            step.repair = form_text(form, "repair", step.repair)
        if "performed_by" in form:
            step.performed_by = form_text(form, "performed_by", step.performed_by)
        if "is_done" in form:
            step.is_done = parse_bool(form_text(form, "is_done", None), step.is_done)

        photo_1 = form.get("extra_photo_1")
        if hasattr(photo_1, "filename") and photo_1.filename:
            _, step.extra_photo_1 = await save_upload_file(photo_1, media_dir="media/service_guides")

        photo_2 = form.get("extra_photo_2")
        if hasattr(photo_2, "filename") and photo_2.filename:
            _, step.extra_photo_2 = await save_upload_file(photo_2, media_dir="media/service_guides")
    else:
        payload = ServiceGuideStepUpdate.model_validate(await request.json())
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(step, key, value)

    step.updated_at = datetime.utcnow()
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.delete("/{guide_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_guide_step(guide_id: int, step_id: int, db: db_dependency):
    step = get_step_or_404(db, guide_id, step_id)
    db.delete(step)
    db.commit()
    return
