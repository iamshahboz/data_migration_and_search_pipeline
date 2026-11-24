"""FastAPI app: search and filter the records stored in PostgreSQL.

Run:
    uvicorn api:app --reload
Docs:
    http://127.0.0.1:8000/docs
"""
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import db
from models import AgencyRecord
from schemas import Category, Status

MAX_LIMIT = 50


# ----------------------------- response models -----------------------------
class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    agency_name: str
    district: str
    category: Category
    status: Status
    text: str


class RecordPage(BaseModel):
    total: int  # all records matching the filters (not just this page)
    limit: int
    offset: int
    results: list[RecordOut]


# ------------------------------ app + database ------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set (put it in .env or the environment)")
    app.state.engine = db.get_engine(database_url)
    db.create_tables(app.state.engine)  # empty table if the loader hasn't run yet
    yield
    app.state.engine.dispose()


app = FastAPI(title="Agency Records API", lifespan=lifespan)


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


# --------------------------------- endpoints ---------------------------------
@app.get("/records", response_model=RecordPage)
def list_records(
    agency_name: str | None = Query(None, description="Case-insensitive, partial match"),
    district: str | None = Query(None, description="Case-insensitive, partial match"),
    status: Status | None = Query(None, description="Exact value"),
    date_from: date | None = Query(None, description="Period start, inclusive (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Period end, inclusive (YYYY-MM-DD)"),
    date_field: Literal["created_at", "updated_at"] = Query(
        "created_at", description="Which date the period applies to"),
    limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT, description=f"Max {MAX_LIMIT}"),
    offset: int = Query(0, ge=0, description="Skip this many records (for paging)"),
    session: Session = Depends(get_session),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")

    conditions = []
    if agency_name:
        conditions.append(AgencyRecord.agency_name.icontains(agency_name, autoescape=True))
    if district:
        conditions.append(AgencyRecord.district.icontains(district, autoescape=True))
    if status:
        conditions.append(AgencyRecord.status == status)

    date_column = getattr(AgencyRecord, date_field)
    if date_from:
        conditions.append(date_column >= datetime.combine(date_from, time.min))
    if date_to:  # inclusive: everything before the start of the next day
        conditions.append(date_column < datetime.combine(date_to + timedelta(days=1), time.min))

    total = session.scalar(select(func.count()).select_from(AgencyRecord).where(*conditions))
    rows = session.scalars(
        select(AgencyRecord).where(*conditions)
        .order_by(AgencyRecord.id).limit(limit).offset(offset)
    ).all()
    return RecordPage(total=total, limit=limit, offset=offset, results=rows)