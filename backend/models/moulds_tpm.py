# models/moulds_tpm.py
from datetime import date
from enum import IntEnum
from sqlalchemy import Column, Integer, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base

class CzasReakcji(IntEnum):
    NATYCHMIAST = 0
    W_TRKACIE_PRZEGLADU = 1
    PO_ZAKONCZONEJ_PRODUKCJI = 2

class Statusy(IntEnum):
    OTWARTY = 0
    W_TRAKCIE_REALIZACJI = 1
    ZAMKNIĘTY = 2
    ODRZUCONY = 3

class MouldsTpm(Base):
    __tablename__ = "moulds_tpm"

    id = Column(Integer, primary_key=True, index=True)
    mould_id = Column(Integer, ForeignKey("moulds.id", ondelete="CASCADE"), nullable=False)
    sv = Column(Integer, nullable=True, default=0)
    created = Column(Date, nullable=False, default=date.today)
    extra_photo_1 = Column(Text, nullable=True)
    extra_photo_2 = Column(Text, nullable=True)
    tpm_time_type = Column(Integer, nullable=False, default=CzasReakcji.NATYCHMIAST.value)
    opis_zgloszenia = Column(Text, nullable=True)
    ido = Column(Integer, nullable=True, default=0)
    status = Column(Integer, nullable=False, default=Statusy.OTWARTY.value)
    changed = Column(Date, nullable=True, default=date(1900, 1, 1))
    author = Column(Text, nullable=True)

    mould = relationship("Mould", back_populates="tpm")

    def name_with_description(self) -> str:
        return f"{self.created} / {self.mould_id} / {self.opis_zgloszenia}"
