import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class UserDailyStats(Base):
    __tablename__ = "user_daily_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    queries_count = Column(Integer, nullable=False, default=0)
    documents_uploaded = Column(Integer, nullable=False, default=0)
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class OrgMonthlyStats(Base):
    __tablename__ = "org_monthly_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    year_month = Column(String(7), nullable=False)
    queries_count = Column(Integer, nullable=False, default=0)
    documents_uploaded = Column(Integer, nullable=False, default=0)
    active_users = Column(Integer, nullable=False, default=0)
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    top_features = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True)
    faithfulness_score = Column(Numeric(4, 3), nullable=True)
    relevance_score = Column(Numeric(4, 3), nullable=True)
    citation_score = Column(Numeric(4, 3), nullable=True)
    trajectory_score = Column(Numeric(4, 3), nullable=True)
    tool_use_score = Column(Numeric(4, 3), nullable=True)
    evaluation_type = Column(String(50), nullable=False)
    passed = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class FeatureUsage(Base):
    __tablename__ = "feature_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=True, index=True)
    feature_name = Column(String(100), nullable=False)
    used_at = Column(DateTime, nullable=False, server_default=func.now())