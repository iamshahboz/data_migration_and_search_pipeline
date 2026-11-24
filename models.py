"""SQLAlchemy ORM model: defines the database table (no raw SQL needed)."""
from datetime import datetime
from typing import get_args

from sqlalchemy import CheckConstraint, Enum, String, Text, column
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