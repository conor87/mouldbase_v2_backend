from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from db.database import Base


class ServiceWorkstation(Base):
    __tablename__ = "stanowiska_service"

    id = Column(Integer, primary_key=True, index=True)
    nazwa_stanowiska = Column(String(100), nullable=False, unique=True)
    st = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    aktualne_przezbrojenie_id = Column(Integer, nullable=True)
    aktualne_zlecenie_serwisowe_id = Column(Integer, nullable=True)
    aktualny_typ_zlecenia = Column(String(100), nullable=True)
    status_changeovers = Column(String(50), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ServiceLog(Base):
    __tablename__ = "service_log"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(100), nullable=True)
    created_at = Column(String(50), nullable=True)
    status_service = Column(String(50), nullable=True)
    mes_activ_service_id = Column(Integer, nullable=True)
    mes_activ_changeover_id = Column(Integer, nullable=True)
    status_changeover = Column(String(50), nullable=True)
