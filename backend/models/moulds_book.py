# models/moulds_tpm.py
from datetime import date
from enum import IntEnum
from sqlalchemy import Column, Integer, Text, Date, ForeignKey, text
from sqlalchemy.orm import relationship
from db.database import Base

class TpmType(IntEnum):
    AWARIA = 0
    TPM = 1
    PRZEZBROJENIE = 2

class MouldsBook(Base):
    __tablename__ = "mouldbase_mouldsbook"

    id = Column(Integer, primary_key=True, index=True)
    mould_id = Column("mould_id_id", Integer, ForeignKey("moulds.id", ondelete="CASCADE"), nullable=False)
    sv = Column(Integer, nullable=True, default=0)
    created = Column(Date, nullable=False, default=date.today)
    extra_photo_1 = Column(Text, nullable=True)
    extra_photo_2 = Column(Text, nullable=True)
    czas_trwania = Column(Integer, nullable=True, default=0)
    czas_wylaczenia = Column(Integer, nullable=True, default=0)
    tpm_type = Column(Integer, nullable=False, default=TpmType.AWARIA.value)
    status = Column(Integer, nullable=False, server_default=text("0"))
    opis_zgloszenia = Column(Text, nullable=True)
    ido = Column(Integer, nullable=True, default=0)

    mould = relationship("Mould", back_populates="book")

    def name_with_description(self) -> str:
        return f"{self.created} / {self.mould_id} / {self.opis_zgloszenia}"
