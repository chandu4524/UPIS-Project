from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database.base import Base


class OcrDocument(Base):
    __tablename__ = "ocr_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(512), nullable=False)
    extracted_text = Column(Text, nullable=False, default="")
    confidence_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
