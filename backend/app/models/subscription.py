import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    organisation_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    plan = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    queries_per_day = Column(Integer, nullable=False)
    queries_per_month = Column(Integer, nullable=False)
    max_documents = Column(Integer, nullable=False)
    max_pages_per_doc = Column(Integer, nullable=False)
    max_file_size_mb = Column(Integer, nullable=False)
    storage_limit_mb = Column(Integer, nullable=False)
    stripe_subscription_id = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND organisation_id IS NULL) OR (user_id IS NULL AND organisation_id IS NOT NULL)",
            name="one_subscriber",
        ),
    )
