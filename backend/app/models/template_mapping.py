from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


class TemplateMapping(Base):
    __tablename__ = "template_mappings"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(255), nullable=False, index=True)
    mapping_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
