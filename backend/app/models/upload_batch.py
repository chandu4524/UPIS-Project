from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


class UploadBatch(Base):
    """Parent batch for bulk multi-file ingestion."""

    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    total_files = Column(Integer, nullable=False, default=0)
    completed_files = Column(Integer, nullable=False, default=0)
    failed_files = Column(Integer, nullable=False, default=0)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notes = Column(Text, nullable=True)


class UploadBatchFile(Base):
    """Per-file status within a bulk upload batch."""

    __tablename__ = "upload_batch_files"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, nullable=False, index=True)
    upload_id = Column(Integer, nullable=True, index=True)

    filename = Column(String(512), nullable=False)
    file_format = Column(String(16), nullable=False, index=True)
    source_type = Column(String(64), nullable=False, default="general", index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)

    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    partial_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    rows_imported = Column(Integer, nullable=False, default=0)

    error_message = Column(Text, nullable=True)
    column_mapping_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
