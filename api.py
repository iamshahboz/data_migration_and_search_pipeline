"""FastAPI app: search, filter and summarise the records stored in PostgreSQL.

Run:
    uvicorn api:app --reload
Docs:
    http://127.0.0.1:8000/docs

Endpoints:
    GET /records     filter by agency_name, district, status and period
    GET /search      text search in the `text` field
    GET /statistics  number of records per agency_name and status for a period
"""
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import db
from models import AgencyRecord
from schemas import Category, Status

MAX_LIMIT = 50

# Query parameters shared by several endpoints
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT, description=f"Max {MAX_LIMIT}")]
Offset = Annotated[int, Query(ge=0, description="Skip this many results (for paging)")]
DateFrom = Annotated[date | None, Query(description="Period start, inclusive (YYYY-MM-DD)")]
DateTo = Annotated[date | None, Query(description="Period end, inclusive (YYYY-MM-DD)")]
DateField = Annotated[Literal["created_at", "updated_at"],
                      Query(description="Which date the period applies to")]


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
    total: int  # all records matching the request (not just this page)
    limit: int
    offset: int
    results: list[RecordOut]


class StatRow(BaseModel):
    agency_name: str
    status: Status
    count: int


class StatsPage(BaseModel):
    total: int  # number of (agency_name, status) rows for the period
    limit: int
    offset: int
    results: list[StatRow]


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


def period_conditions(date_from: date | None, date_to: date | None, date_field: str) -> list:
    """SQL conditions for an inclusive period on created_at / updated_at."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    column = getattr(AgencyRecord, date_field)
    conditions = []
    if date_from:
        conditions.append(column >= datetime.combine(date_from, time.min))
    if date_to:  # inclusive: everything before the start of the next day
        conditions.append(column < datetime.combine(date_to + timedelta(days=1), time.min))
    return conditions


def fetch_page(session: Session, conditions: list, limit: int, offset: int) -> RecordPage:
    total = session.scalar(select(func.count()).select_from(AgencyRecord).where(*conditions))
    rows = session.scalars(
        select(AgencyRecord).where(*conditions)
        .order_by(AgencyRecord.id).limit(limit).offset(offset)
    ).all()
    return RecordPage(total=total, limit=limit, offset=offset, results=rows)


# --------------------------------- endpoints ---------------------------------
@app.get("/records", response_model=RecordPage)
def list_records(
    agency_name: str | None = Query(None, description="Case-insensitive, partial match"),
    district: str | None = Query(None, description="Case-insensitive, partial match"),
    status: Status | None = Query(None, description="Exact value"),
    date_from: DateFrom = None,
    date_to: DateTo = None,
    date_field: DateField = "created_at",
    limit: Limit = MAX_LIMIT,
    offset: Offset = 0,
    session: Session = Depends(get_session),
):
    conditions = period_conditions(date_from, date_to, date_field)
    if agency_name:
        conditions.append(AgencyRecord.agency_name.icontains(agency_name, autoescape=True))
    if district:
        conditions.append(AgencyRecord.district.icontains(district, autoescape=True))
    if status:
        conditions.append(AgencyRecord.status == status)
    return fetch_page(session, conditions, limit, offset)


@app.get("/search", response_model=RecordPage)
def search_text(
    q: str = Query(..., min_length=1, max_length=100,
                   description="Words to look for in `text`: case-insensitive, "
                               "all words must appear, in any order"),
    limit: Limit = MAX_LIMIT,
    offset: Offset = 0,
    session: Session = Depends(get_session),
):
    terms = q.split()
    if not terms:
        raise HTTPException(status_code=422, detail="q must contain at least one word")
    conditions = [AgencyRecord.text.icontains(term, autoescape=True) for term in terms]
    return fetch_page(session, conditions, limit, offset)


@app.get("/statistics", response_model=StatsPage)
def statistics(
    date_from: DateFrom = None,
    date_to: DateTo = None,
    date_field: DateField = "created_at",
    limit: Limit = MAX_LIMIT,
    offset: Offset = 0,
    session: Session = Depends(get_session),
):
    """Number of records per agency_name and status; no period = all time."""
    conditions = period_conditions(date_from, date_to, date_field)
    grouped = (
        select(AgencyRecord.agency_name, AgencyRecord.status, func.count().label("count"))
        .where(*conditions)
        .group_by(AgencyRecord.agency_name, AgencyRecord.status)
    )
    total = session.scalar(select(func.count()).select_from(grouped.subquery()))
    rows = session.execute(
        grouped.order_by(AgencyRecord.agency_name, AgencyRecord.status)
        .limit(limit).offset(offset)
    ).all()
    results = [StatRow(**dict(row._mapping)) for row in rows]
    return StatsPage(total=total, limit=limit, offset=offset, results=results)