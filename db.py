"""Database helpers built on SQLAlchemy: engine, table creation, batch insert."""
import logging

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from models import AgencyRecord, Base
from schemas import Record

logger = logging.getLogger(__name__)


def get_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.drivername == "postgresql":  # use psycopg (v3) instead of the default psycopg2
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(url)


def create_tables(engine: Engine) -> None:
    """Create the table(s) defined in models.py if they don't exist yet."""
    Base.metadata.create_all(engine)
    logger.info("Connected to database '%s' on host '%s'; tables ready (%s)",
                engine.url.database, engine.url.host, AgencyRecord.__tablename__)


def insert_batch(engine: Engine, records: list[Record]) -> int:
    """Insert validated records in one transaction.

    Rows whose id already exists are skipped (ON CONFLICT DO NOTHING).
    Returns the number of rows actually inserted.
    """
    rows = [record.model_dump() for record in records]
    stmt = (
        insert(AgencyRecord)
        .on_conflict_do_nothing(index_elements=[AgencyRecord.id])
        .returning(AgencyRecord.id)
    )
    with Session(engine) as session, session.begin():  # commit, or rollback on error
        return len(session.execute(stmt, rows).all())