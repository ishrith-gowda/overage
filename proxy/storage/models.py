"""SQLAlchemy 2.0 ORM models and Pydantic schemas for the Overage database.

Every table matches the schema in PRD.md Section 4 (Data Models).
Pydantic schemas are used for API request/response serialization.
Reference: INSTRUCTIONS.md Section 10 (Database Patterns).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# SQLAlchemy Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class User(Base):
    """Overage user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    api_keys: Mapped[list[APIKey]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    call_logs: Mapped[list[APICallLog]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class APIKey(Base):
    """Hashed API key for authenticating Overage API requests."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default Key")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey id={self.id} user_id={self.user_id} active={self.is_active}>"

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new raw API key and its SHA-256 hash.

        Returns:
            Tuple of (raw_key, key_hash). The raw key is returned to the user
            exactly once; only the hash is stored.
        """
        raw_key = f"ovg_live_{secrets.token_hex(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, key_hash

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash a raw API key with SHA-256.

        Args:
            raw_key: The plaintext API key.

        Returns:
            The hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(raw_key.encode()).hexdigest()


class APICallLog(Base):
    """Record of a single API call proxied through Overage."""

    __tablename__ = "api_call_logs"
    __table_args__ = (
        Index("idx_call_logs_user_provider", "user_id", "provider"),
        Index("idx_call_logs_user_timestamp", "user_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(
        String(255), nullable=False, default="/v1/chat/completions"
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_length_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answer_length_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reported_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reported_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reported_reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_usage_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    user: Mapped[User] = relationship(back_populates="call_logs")
    estimation: Mapped[EstimationResult | None] = relationship(
        back_populates="call_log", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<APICallLog id={self.id} provider={self.provider!r} "
            f"model={self.model!r} reasoning={self.reported_reasoning_tokens}>"
        )


class EstimationResult(Base):
    """Independent estimation of reasoning tokens for a single API call."""

    __tablename__ = "estimation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("api_call_logs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    palace_estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    palace_confidence_low: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    palace_confidence_high: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    palace_model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v0.1.0")
    timing_estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timing_tps_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timing_r_squared: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discrepancy_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    dollar_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    signals_agree: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    domain_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    call_log: Mapped[APICallLog] = relationship(back_populates="estimation")

    def __repr__(self) -> str:
        return (
            f"<EstimationResult call_id={self.call_id} "
            f"combined={self.combined_estimated_tokens} discrepancy={self.discrepancy_pct:.1f}%>"
        )


class DiscrepancyAlert(Base):
    """Alert generated when aggregate discrepancy exceeds a threshold."""

    __tablename__ = "discrepancy_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_discrepancy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    dollar_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    threshold_pct: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    alert_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<DiscrepancyAlert id={self.id} "
            f"discrepancy={self.aggregate_discrepancy_pct:.1f}% status={self.alert_status!r}>"
        )


# ---------------------------------------------------------------------------
# Pydantic Schemas (API request/response serialization)
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: str = Field(..., min_length=3, max_length=255, description="User email")
    name: str = Field(..., min_length=1, max_length=255, description="Display name")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")


class UserRead(BaseModel):
    """Schema for user data in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    created_at: datetime


class APICallLogRead(BaseModel):
    """Schema for call log data in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    model: str
    reported_input_tokens: int
    reported_output_tokens: int
    reported_reasoning_tokens: int
    total_latency_ms: float
    ttft_ms: float | None
    is_streaming: bool
    timestamp: datetime
    request_id: str


class EstimationResultRead(BaseModel):
    """Schema for estimation data in API responses."""

    model_config = ConfigDict(from_attributes=True)

    palace_estimated_tokens: int
    palace_confidence_low: int
    palace_confidence_high: int
    palace_model_version: str
    timing_estimated_tokens: int
    timing_tps_used: float
    timing_r_squared: float | None
    combined_estimated_tokens: int
    discrepancy_pct: float
    dollar_impact: float
    signals_agree: bool
    domain_classification: str | None
    estimated_at: datetime


class CallDetailRead(BaseModel):
    """Combined call log + estimation for the detail endpoint."""

    model_config = ConfigDict(from_attributes=True)

    call: APICallLogRead
    estimation: EstimationResultRead | None = None


class SummaryStats(BaseModel):
    """Aggregate statistics for the summary endpoint."""

    total_calls: int = 0
    total_reported_reasoning_tokens: int = 0
    total_estimated_reasoning_tokens: int = 0
    aggregate_discrepancy_pct: float = 0.0
    total_dollar_impact: float = 0.0
    avg_discrepancy_pct: float = 0.0
    honoring_rate_pct: float = 0.0


class SummaryGroupRow(BaseModel):
    """Per-group aggregates when ``group_by`` is set on ``GET /v1/summary`` (PRD Story 8)."""

    group_key: str = Field(..., description="Stable key: provider, model, or provider::model")
    provider: str | None = None
    model: str | None = None
    call_count: int = 0
    total_reported_reasoning_tokens: int = 0
    total_estimated_reasoning_tokens: int = 0
    aggregate_discrepancy_pct: float = 0.0
    avg_discrepancy_pct: float = 0.0
    total_dollar_impact: float = 0.0
    low_confidence: bool = Field(
        default=False,
        description="True when call_count < 10 for this group",
    )


class SummaryWithGroups(BaseModel):
    """Summary response when ``group_by`` is used: overall plus grouped rows."""

    overall: SummaryStats
    groups: list[SummaryGroupRow]


class DiscrepancyAlertRead(BaseModel):
    """Discrepancy alert row for ``GET /v1/alerts``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    window_start: datetime
    window_end: datetime
    call_count: int
    aggregate_discrepancy_pct: float
    dollar_impact: float
    confidence_level: str
    threshold_pct: float
    alert_status: str
    acknowledged_at: datetime | None
    created_at: datetime


class TimeseriesPoint(BaseModel):
    """A single data point for the time-series chart endpoint."""

    date: str
    call_count: int = 0
    reported_reasoning_tokens: int = 0
    estimated_reasoning_tokens: int = 0
    discrepancy_pct: float = 0.0
    dollar_impact: float = 0.0


class APIKeyCreate(BaseModel):
    """Schema for API key generation request."""

    name: str = Field(default="Default Key", max_length=255, description="Key display name")


class APIKeyRead(BaseModel):
    """Schema for the API key response (returned once, includes raw key)."""

    key: str = Field(..., description="Raw API key (shown only once)")
    name: str
    created_at: datetime


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    error_code: str
    detail: str | None = None
    request_id: str | None = None
