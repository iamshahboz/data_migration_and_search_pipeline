"""Load a JSON file of records into PostgreSQL.

Every record is validated with Pydantic; invalid and duplicate records are
skipped (and logged), valid ones are inserted in batches.

Usage:
    python load_data.py --input output.json
    python load_data.py --input output.json --batch-size 200 --log-level DEBUG
"""
import argparse
import json
import logging
import os
import sys
import time

from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

import db
from schemas import Record

logger = logging.getLogger("load_data")


def setup_logging(level: str, log_file: str) -> None:
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    handlers = [logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")]
    root = logging.getLogger()
    root.setLevel(level)
    for handler in handlers:
        handler.setFormatter(fmt)
        root.addHandler(handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load JSON records into PostgreSQL.")
    parser.add_argument("--input", default="output.json",
                        help="Input JSON file (default: output.json)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Records per insert transaction (default: 500)")
    parser.add_argument("--database-url", default=None,
                        help="PostgreSQL URL (default: DATABASE_URL env var / .env file)")
    parser.add_argument("--skipped-file", default="skipped_records.json",
                        help="JSON file for skipped (wrong) records (default: skipped_records.json)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level (default: INFO)")
    parser.add_argument("--log-file", default="load.log",
                        help="Log file (default: load.log)")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be a positive integer")
    return args


def read_records(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON file must contain a list of records")
    return data


def describe_errors(exc: ValidationError) -> str:
    """Short human-readable reason for a validation failure."""
    missing, problems = [], []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"]) or "record"
        if err["type"] == "missing":
            missing.append(field)
        else:
            problems.append(f"{field}: {err['msg']}")
    parts = []
    if missing:
        parts.append(f"missing fields {missing}")
    if problems:
        parts.append("; ".join(problems))
    return " | ".join(parts)


def short_reasons(exc: ValidationError) -> str:
    """Very short reason for the skipped-records file."""
    reasons = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"])
        if err["type"] == "missing":
            reasons.append(f"missing field: {field}")
        elif not field:  # model-level check, e.g. updated_at earlier than created_at
            reasons.append(err["msg"].removeprefix("Value error, "))
        elif field in ("created_at", "updated_at"):
            reasons.append(f"bad date format: {field}")
        else:
            reasons.append(f"invalid value: {field}")
    return "; ".join(reasons)


def duplicate_reason(raw: dict, first_position: int, first_raw: dict) -> str:
    if raw == first_raw:
        return f"exact duplicate of record #{first_position}"
    changed = sorted(k for k in set(raw) | set(first_raw) if raw.get(k) != first_raw.get(k))
    return f"same id as record #{first_position}, differs in: {', '.join(changed)}"


def skipped_entry(raw, reason: str) -> dict:
    """The record exactly as it was in the input, plus one extra key: reason."""
    if isinstance(raw, dict):
        return {**raw, "reason": reason}
    return {"value": raw, "reason": reason}  # input item wasn't even an object


def write_skipped(path: str, skipped: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(skipped, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d skipped records to '%s'", len(skipped), path)


def load(engine: Engine, raw_records: list, batch_size: int) -> tuple[dict, list]:
    stats = {"total": len(raw_records), "inserted": 0, "invalid": 0,
             "duplicates": 0, "already_in_db": 0}
    batch: list[Record] = []
    seen: dict[int, tuple[int, dict]] = {}  # id -> (position, raw) of first occurrence
    skipped: list[dict] = []
    existing_ids = db.get_existing_ids(engine)
    logger.info("Found %d records already in the database", len(existing_ids))

    def flush() -> None:
        if not batch:
            return
        inserted = db.insert_batch(engine, batch)
        stats["inserted"] += inserted
        stats["already_in_db"] += len(batch) - inserted
        logger.info("Batch inserted: %d of %d records (total inserted so far: %d)",
                    inserted, len(batch), stats["inserted"])
        batch.clear()

    for position, raw in enumerate(raw_records, start=1):
        label = f"Record #{position}"
        if isinstance(raw, dict) and "id" in raw:
            label += f" (id={raw['id']!r})"

        try:
            record = Record.model_validate(raw)
        except ValidationError as exc:
            stats["invalid"] += 1
            logger.warning("%s skipped - invalid: %s", label, describe_errors(exc))
            skipped.append(skipped_entry(raw, short_reasons(exc)))
            continue

        if record.id in seen:
            stats["duplicates"] += 1
            first_position, first_raw = seen[record.id]
            reason = duplicate_reason(raw, first_position, first_raw)
            logger.warning("%s skipped - duplicate: %s", label, reason)
            skipped.append(skipped_entry(raw, reason))
            continue
        seen[record.id] = (position, raw)

        if record.id in existing_ids:  # migrated in a previous run: no DB write at all
            stats["already_in_db"] += 1
            logger.debug("%s skipped - already in database", label)
            continue

        batch.append(record)
        if len(batch) >= batch_size:
            flush()

    flush()  # remaining records
    return stats, skipped


def log_summary(stats: dict, duration: float) -> None:
    skipped = stats["invalid"] + stats["duplicates"]
    logger.info("---------------- SUMMARY ----------------")
    logger.info("Total read:           %d", stats["total"])
    logger.info("Inserted:             %d", stats["inserted"])
    logger.info("Skipped:              %d", skipped)
    logger.info("  - validation:       %d  (missing fields / bad dates / bad values)", stats["invalid"])
    logger.info("  - duplicates:       %d", stats["duplicates"])
    if stats["already_in_db"]:
        logger.info("Already in database:  %d  (ids existed from a previous run)", stats["already_in_db"])
    if stats["inserted"] == 0 and stats["already_in_db"] > 0:
        logger.info("Data already migrated - nothing new to insert, database unchanged.")
    logger.info("Duration:             %.2fs", duration)


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level, args.log_file)
    load_dotenv()

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("No database URL: set DATABASE_URL (env var or .env) or use --database-url")
        return 1

    start = time.perf_counter()
    try:
        raw_records = read_records(args.input)
    except (OSError, ValueError) as exc:  # includes FileNotFoundError, JSONDecodeError
        logger.error("Could not read '%s': %s", args.input, exc)
        return 1
    logger.info("Read %d records from '%s'", len(raw_records), args.input)

    engine = db.get_engine(database_url)
    try:
        db.create_tables(engine)
        stats, skipped = load(engine, raw_records, args.batch_size)
    except SQLAlchemyError:
        logger.exception("Database error - the failed batch was rolled back, stopping")
        return 1
    finally:
        engine.dispose()

    try:
        write_skipped(args.skipped_file, skipped)
    except OSError as exc:
        logger.error("Could not write skipped records to '%s': %s", args.skipped_file, exc)

    log_summary(stats, time.perf_counter() - start)
    return 0


if __name__ == "__main__":
    sys.exit(main())