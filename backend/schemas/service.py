from typing import Optional

from pydantic import BaseModel, ConfigDict


class ServiceWorkstationBase(BaseModel):
    nazwa_stanowiska: str
    st: Optional[str] = None
    status: Optional[str] = None
    aktualne_przezbrojenie_id: Optional[int] = None
    aktualne_zlecenie_serwisowe_id: Optional[int] = None
    aktualny_typ_zlecenia: Optional[str] = None
    status_changeovers: Optional[str] = None
    user_id: Optional[int] = None


class ServiceWorkstationCreate(ServiceWorkstationBase):
    pass


class ServiceWorkstationUpdate(BaseModel):
    nazwa_stanowiska: Optional[str] = None
    st: Optional[str] = None
    status: Optional[str] = None
    aktualne_przezbrojenie_id: Optional[int] = None
    aktualne_zlecenie_serwisowe_id: Optional[int] = None
    aktualny_typ_zlecenia: Optional[str] = None
    status_changeovers: Optional[str] = None
    user_id: Optional[int] = None


class ServiceWorkstationRead(ServiceWorkstationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ─── Service Log ──────────────────────────────────────────────────────────────

class ServiceLogBase(BaseModel):
    operator: Optional[str] = None
    created_at: Optional[str] = None
    status_service: Optional[str] = None
    mes_activ_service_id: Optional[int] = None
    mes_activ_changeover_id: Optional[int] = None
    status_changeover: Optional[str] = None


class ServiceLogCreate(ServiceLogBase):
    pass


class ServiceLogUpdate(BaseModel):
    operator: Optional[str] = None
    created_at: Optional[str] = None
    status_service: Optional[str] = None
    mes_activ_service_id: Optional[int] = None
    mes_activ_changeover_id: Optional[int] = None
    status_changeover: Optional[str] = None


class ServiceLogRead(ServiceLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
