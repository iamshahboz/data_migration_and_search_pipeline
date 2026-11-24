"""Pydantic schema used to validate every record before it reaches the database."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"  # e.g. 2026-03-14T09:21:00
NAME_MAX_LENGTH = 100

Category = Literal["normal", "urgent", "critical"]
Status = Literal["open", "in_progress", "closed"]


class Record(BaseModel):
    # strict: no silent type coercion ("5" is not an int, 1741942860 is not a date)
    model_config = ConfigDict(strict=True, extra="ignore")

    id: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime
    agency_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    district: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    category: Category
    status: Status
    text: str = Field(min_length=1)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_date(cls, value):
        """Accept only strings in the exact format YYYY-MM-DDTHH:MM:SS."""
        if not isinstance(value, str):
            raise ValueError(f"date must be a string like 2026-03-14T09:21:00, got {value!r}")
        try:
            return datetime.strptime(value, DATE_FORMAT)
        except ValueError:
            raise ValueError(
                f"invalid date {value!r}, expected format YYYY-MM-DDTHH:MM:SS"
            ) from None

    @model_validator(mode="after")
    def check_date_order(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at is earlier than created_at")
        return self