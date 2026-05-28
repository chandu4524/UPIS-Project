from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


class PersonStaging(Base):
    __tablename__ = "person_staging"

    id = Column(Integer, primary_key=True, index=True)
    upload_batch_id = Column(Integer, index=True, nullable=False)
    row_number = Column(Integer, nullable=False)

    raw_json = Column(Text, nullable=False, default="{}")
    normalized_json = Column(Text, nullable=False, default="{}")

    full_name = Column(String)
    normalized_name = Column(String)
    gender = Column(String)
    dob = Column(String)
    father_name = Column(String)
    spouse_name = Column(String)
    mobile = Column(String)

    address = Column(String)
    village = Column(String)
    district = Column(String)

    aadhaar_token = Column(String)
    pan_token = Column(String)

    source_name = Column(String)
    department_name = Column(String)

    confidence_level = Column(String(16), nullable=False, default="LOW", index=True)
    validation_errors = Column(Text, nullable=False, default="[]")
    extraction_status = Column(String(32), nullable=False, default="staged", index=True)

    matching_key = Column(String, index=True)
    mobile_hash = Column(String, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

