from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from db.database import Base


class ServiceGuide(Base):
    __tablename__ = "service_guides"

    id = Column(Integer, primary_key=True, index=True)
    mould_id = Column(Integer, nullable=True, index=True)
    guide_number = Column(Text, nullable=False, index=True)
    product_name = Column(Text, nullable=False, default="")
    review_date = Column(Date, nullable=True, default=date.today)
    review_reason = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    steps = relationship(
        "ServiceGuideStep",
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="ServiceGuideStep.lp",
    )


class ServiceGuideStep(Base):
    __tablename__ = "service_guide_steps"

    id = Column(Integer, primary_key=True, index=True)
    guide_id = Column(Integer, ForeignKey("service_guides.id", ondelete="CASCADE"), nullable=False, index=True)
    lp = Column(Integer, nullable=False, default=1)
    fault = Column(Text, nullable=True)
    confirmed_by = Column(Text, nullable=True)
    repair = Column(Text, nullable=True)
    performed_by = Column(Text, nullable=True)
    extra_photo_1 = Column(Text, nullable=True)
    extra_photo_2 = Column(Text, nullable=True)
    is_done = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    guide = relationship("ServiceGuide", back_populates="steps")
