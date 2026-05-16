import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.core.database import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rollout_percentage = Column(Integer, nullable=False, default=0)
    enabled_for_tiers = Column(ARRAY(String), nullable=False, default=list)
    enabled_for_users = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())