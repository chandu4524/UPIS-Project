from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database.base import Base


class PersonRelationship(Base):
    __tablename__ = "person_relationships"

    id = Column(Integer, primary_key=True, index=True)
    citizen_id = Column(Integer, nullable=False, index=True)

    related_entity_type = Column(String(64), nullable=False, index=True)
    related_entity_value = Column(String(512), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False, index=True)

    confidence_score = Column(Integer, nullable=False, default=0, index=True)
    source_name = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

