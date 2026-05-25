from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


class EntityReview(Base):
    __tablename__ = "entity_reviews"

    id = Column(Integer, primary_key=True, index=True)
    citizen_a_id = Column(Integer, nullable=False, index=True)
    citizen_b_id = Column(Integer, nullable=False, index=True)
    match_score = Column(Integer, nullable=False, default=0)
    match_reasons = Column(Text, nullable=False, default="[]")
    category = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
