from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import db_dependency
from models.settings import SystemSetting
from routers.auth import superadmin_required

router = APIRouter(prefix="/settings", tags=["settings"])

def get_setting_value(db: Session, key: str, default: str) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        return default
    return setting.value

def set_setting_value(db: Session, key: str, value: str):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
    db.commit()

@router.get("/auto-logout")
def get_auto_logout_status(db: db_dependency):
    val = get_setting_value(db, "auto_logout_enabled", "true")
    return {"enabled": val == "true"}

@router.put("/auto-logout", dependencies=[Depends(superadmin_required)])
def update_auto_logout_status(payload: dict, db: db_dependency):
    enabled = payload.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Missing 'enabled' field")
    val = "true" if enabled else "false"
    set_setting_value(db, "auto_logout_enabled", val)
    return {"enabled": enabled}
