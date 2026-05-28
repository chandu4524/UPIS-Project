from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id = Column(Integer, primary_key=True, index=True)
    staging_id = Column(Integer, nullable=False, index=True)
    citizen_id = Column(Integer, nullable=True, index=True)

    matched_person_key = Column(String, nullable=True, index=True)
    confidence_score = Column(Integer, nullable=False, default=0, index=True)
    match_category = Column(String(32), nullable=False, index=True)
    match_reasons = Column(Text, nullable=False, default="[]")

    review_status = Column(String(32), nullable=False, default="pending", index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

