# models/mould.py
from datetime import date
from enum import IntEnum
from sqlalchemy import Column, Integer, String, Text, Date, Boolean
from sqlalchemy.orm import relationship
from db.database import Base

class PobytFormy(IntEnum):
    PRODUKCJA = 0
    NARZEDZIOWNIA = 1
    KOOPERACJA = 2
    MAGAZYN_FORM = 3

class StanFormy(IntEnum):
    PRODUKCYJNA = 0
    TPM = 1
    AWARIA = 2
    MODYFIKACJA = 3
    PRZEZBRAJANA = 4
    W_PRZEGLADZIE = 5

class Mould(Base):
    __tablename__ = "moulds"

    id = Column(Integer, primary_key=True, index=True)
    mould_number = Column(String(128), nullable=False, unique=True, index=True)
    product = Column(Text, nullable=False, default="")
    released = Column(Date, nullable=True, default="0000-00-00")
    company = Column(Text, nullable=False, default="Lamela")
    czy_przezbrajalna = Column(Boolean, default="False")

    mould_photo = Column(Text, nullable=True)
    product_photo = Column(Text, nullable=True)
    hot_system_photo = Column(Text, nullable=True)
    extra_photo_1 = Column(Text, nullable=True)
    extra_photo_2 = Column(Text, nullable=True)
    extra_photo_3 = Column(Text, nullable=True)
    extra_photo_4 = Column(Text, nullable=True)
    extra_photo_5 = Column(Text, nullable=True)

    num_of_cavities = Column(String(128), nullable=True)
    tool_weight = Column(String(128), nullable=True)
    total_cycles = Column(Integer, nullable=False, default=0)
    to_maint_cycles = Column(Integer, nullable=False, default=0)
    from_maint_cycles = Column(Integer, nullable=False, default=0)

    place = Column(Integer, nullable=False, default=PobytFormy.PRODUKCJA.value)
    status = Column(Integer, nullable=False, default=StanFormy.PRODUKCYJNA.value)
    
    notes = Column(Text, nullable=True)

    # relacja - MouldsTpm powinien mieć ForeignKey do Mould.id
    tpm = relationship("MouldsTpm", back_populates="mould", cascade="all, delete-orphan")
    book = relationship("MouldsBook", back_populates="mould", cascade="all, delete-orphan")
    
    # w models/mould.py (klasa Mould)
    changeovers_from = relationship("Changeover", foreign_keys="Changeover.from_mould_id", back_populates="from_mould", cascade="all, delete-orphan")
    changeovers_to   = relationship("Changeover", foreign_keys="Changeover.to_mould_id", back_populates="to_mould", cascade="all, delete-orphan")


    def name_with_year(self):
        year = self.released.year if self.released else "n/a"
        return f"{self.mould_number} ({year})"

    def name_with_description(self):
        return f"{self.mould_number} ({self.product})"

    def to_maint(self) -> int:
        try:
            if int(self.to_maint_cycles) == 0:
                return 0
            return int(int(self.from_maint_cycles) / int(self.to_maint_cycles) * 100)
        except Exception:
            return 0

    def jaki_stan_formy(self) -> str:
        try:
            return StanFormy(self.status).name
        except Exception:
            return str(self.status)

    def gdzie_forma(self) -> str:
        try:
            return PobytFormy(self.place).name
        except Exception:
            return str(self.place)

    def sort(self) -> float:
        pct = self.to_maint()
        if pct > 0:
            return 1.0 / pct
        else:
            return 0.1
