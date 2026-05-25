from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database.base import Base


class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    mobile = Column(String)
    district = Column(String)
    village = Column(String)
    dob = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)