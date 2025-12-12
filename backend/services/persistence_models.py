from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")

from .database import Base

class ConfigORM(Base):
    __tablename__ = "configs"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    config = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DataSourceORM(Base):
    __tablename__ = "data_sources"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    path = Column(Text, nullable=True)
    symbol = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    healthy = Column(Boolean, nullable=True)
    last_checked = Column(DateTime, nullable=True)


class RunORM(Base):
    __tablename__ = "runs"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    config_id = Column(String(32), nullable=True)  # Set nullable/FK if ConfigORM usually stays or soft deleted
    config = Column(JSON_TYPE, nullable=False)  # Snapshot of config
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    progress = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    artifacts = Column(JSON_TYPE, default=list)


class AuditLogORM(Base):
    __tablename__ = "audit_logs"

    id = Column(String(32), primary_key=True)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    target = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    detail = Column(Text, nullable=True)
