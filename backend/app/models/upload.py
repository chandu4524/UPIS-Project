from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(512), nullable=False)
    uploaded_rows = Column(Integer, default=0, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
