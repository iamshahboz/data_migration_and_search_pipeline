"""SQLAlchemy ORM model: defines the database table (no raw SQL needed)."""
from datetime import datetime
from typing import get_args

from sqlalchemy import JSON, CheckConstraint, Enum, String, Text, column, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from schemas import NAME_MAX_LENGTH, Category, Status


class Base(DeclarativeBase):
    pass


class AgencyRecord(Base):
    __tablename__ = "agency_records"
    __table_args__ = (
        CheckConstraint(
            column("updated_at") >= column("created_at"),
            name="ck_agency_records_dates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    agency_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    district: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    # VARCHAR + CHECK constraint, allowed values come from the Pydantic schema
    category: Mapped[str] = mapped_column(
        Enum(*get_args(Category), name="ck_agency_records_category",
             native_enum=False, create_constraint=True)
    )
    status: Mapped[str] = mapped_column(
        Enum(*get_args(Status), name="ck_agency_records_status",
             native_enum=False, create_constraint=True)
    )
    text: Mapped[str] = mapped_column(Text)


class McpAuditLog(Base):
    """One row per MCP tool call: who called what, with which parameters, and what came back."""
    __tablename__ = "mcp_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    called_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(100))  # agency the user is limited to, "*" = administrator
    tool: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict] = mapped_column(JSON)
    returned_count: Mapped[int]
    outcome: Mapped[str] = mapped_column(String(20))  # ok | not_found | rate_limited | error
    duration_ms: Mapped[int]
    error: Mapped[str | None] = mapped_column(Text)