from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database.base import Base


class PersonSource(Base):
    __tablename__ = "person_sources"

    id = Column(Integer, primary_key=True, index=True)

    citizen_id = Column(Integer, nullable=False, index=True)
    staging_id = Column(Integer, nullable=True, index=True)
    upload_batch_id = Column(Integer, nullable=True, index=True)

    source_name = Column(String)
    department_name = Column(String)

    confidence_score = Column(Integer, nullable=False, default=0, index=True)
    linked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

