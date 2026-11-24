"""Generate dummy JSON records, including intentionally inaccurate ones.

Usage:
    python script.py --records 500 --inaccurate 20
    python script.py --records 500 --inaccurate 20 --output data.json --seed 42

--records     total number of records in the output (valid + inaccurate)
--inaccurate  how many of those records should be inaccurate
"""
import argparse
import copy
import json
import random
from collections import Counter
from datetime import datetime, timedelta

AGENCIES = [
    "Public Works Department", "Water Authority", "City Police",
    "Fire & Rescue Service", "Health Department", "Transport Agency",
    "Housing Authority", "Environmental Protection Agency",
    "Electricity Board", "Education Department",
]
DISTRICTS = [
    "Central", "North", "South", "East", "West",
    "Riverside", "Hillside", "Old Town", "Industrial Zone", "Harbor",
]
CATEGORIES = ["normal", "urgent", "critical"]
STATUSES = ["open", "in_progress", "closed"]

TEXT_SNIPPETS = [
    "Residents reported an issue that requires investigation.",
    "A team has been dispatched to assess the situation on site.",
    "Follow-up inspection is scheduled for later this week.",
    "The problem has been escalated to the responsible supervisor.",
    "Additional resources are needed to resolve this case.",
    "Citizens have raised multiple complaints about this matter.",
    "Preliminary checks show no immediate danger to the public.",
    "Repair work is pending approval of the allocated budget.",
    "The affected area has been temporarily restricted.",
    "A detailed report will be submitted once the work is complete.",
]

FIELDS = [
    "id", "created_at", "updated_at", "agency_name",
    "district", "category", "status", "text",
]
DATE_FIELDS = ["created_at", "updated_at"]


# --------------------------------------------------------------------------
# Valid records
# --------------------------------------------------------------------------
def random_text() -> str:
    return " ".join(random.sample(TEXT_SNIPPETS, k=random.randint(2, 4)))


def generate_valid_record(record_id: int) -> dict:
    """A fully correct record: all fields present, valid ISO dates."""
    now = datetime.now()
    created_at = now - timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    max_seconds = max(int((now - created_at).total_seconds()), 0)
    updated_at = created_at + timedelta(seconds=random.randint(0, max_seconds))

    return {
        "id": record_id,
        "created_at": created_at.isoformat(timespec="seconds"),
        "updated_at": updated_at.isoformat(timespec="seconds"),
        "agency_name": random.choice(AGENCIES),
        "district": random.choice(DISTRICTS),
        "category": random.choice(CATEGORIES),
        "status": random.choice(STATUSES),
        "text": random_text(),
    }


# --------------------------------------------------------------------------
# Inaccurate records (one function per kind of problem)
# --------------------------------------------------------------------------
def make_missing_fields(record_id: int) -> dict:
    """Valid record with 2-3 random fields removed."""
    record = generate_valid_record(record_id)
    for field in random.sample(FIELDS, k=random.randint(2, 3)):
        del record[field]
    return record


def _bad_date(value: str) -> str:
    """Turn a valid ISO date string into an incorrectly formatted one."""
    dt = datetime.fromisoformat(value)
    formats = [
        dt.strftime("%d/%m/%Y %H:%M"),       # 14/03/2026 09:21
        dt.strftime("%Y/%m/%d"),             # 2026/03/14
        dt.strftime("%B %d, %Y"),            # March 14, 2026
        dt.strftime("%d-%m-%y %I:%M %p"),    # 14-03-26 09:21 AM
        f"{dt.year}-13-45T99:99:99",         # impossible values
        "not a date",
        str(int(dt.timestamp())),            # raw unix timestamp
    ]
    return random.choice(formats)


def make_bad_date_format(record_id: int) -> dict:
    """Valid record where one or both date fields use a wrong format."""
    record = generate_valid_record(record_id)
    for field in random.sample(DATE_FIELDS, k=random.randint(1, 2)):
        record[field] = _bad_date(record[field])
    return record


def make_duplicate_different_updated(source: dict) -> dict:
    """Same record (same id, same data) but with a different updated_at."""
    record = copy.deepcopy(source)
    try:
        original = datetime.fromisoformat(record["updated_at"])
    except (KeyError, ValueError):
        original = datetime.now()
    shift = timedelta(minutes=random.randint(1, 60 * 24 * 30))
    record["updated_at"] = (original + shift).isoformat(timespec="seconds")
    return record


def make_exact_duplicate(source: dict) -> dict:
    """A byte-for-byte copy of an existing record."""
    return copy.deepcopy(source)


def generate_inaccurate_records(count: int, valid_records: list, start_id: int) -> list:
    """Create `count` inaccurate records by randomly picking an error type."""
    inaccurate = []
    next_id = start_id

    for _ in range(count):
        kind = random.choice(
            ["missing_fields", "bad_date", "duplicate_updated", "exact_duplicate"]
        )

        if kind == "missing_fields":
            record = make_missing_fields(next_id)
            next_id += 1
        elif kind == "bad_date":
            record = make_bad_date_format(next_id)
            next_id += 1
        else:
            # Duplicates need a source; fall back to a fresh one if none exist.
            if valid_records:
                source = random.choice(valid_records)
            else:
                source = generate_valid_record(next_id)
                next_id += 1
            if kind == "duplicate_updated":
                record = make_duplicate_different_updated(source)
            else:
                record = make_exact_duplicate(source)

        inaccurate.append((kind, record))

    return inaccurate


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dummy JSON data, including inaccurate records."
    )
    parser.add_argument("--records", type=int, required=True,
                        help="Total number of records (valid + inaccurate)")
    parser.add_argument("--inaccurate", type=int, default=0,
                        help="How many of the total records should be inaccurate (default: 0)")
    parser.add_argument("-o", "--output", default="output.json",
                        help="Output JSON file (default: output.json)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible output")
    args = parser.parse_args()

    if args.records < 1:
        parser.error("--records must be a positive integer")
    if args.inaccurate < 0:
        parser.error("--inaccurate cannot be negative")
    if args.inaccurate > args.records:
        parser.error("--inaccurate cannot be greater than --records")
    return args


def main() -> None:
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    valid_count = args.records - args.inaccurate
    valid_records = [generate_valid_record(i) for i in range(1, valid_count + 1)]

    inaccurate = generate_inaccurate_records(
        args.inaccurate, valid_records, start_id=valid_count + 1
    )

    all_records = valid_records + [record for _, record in inaccurate]
    random.shuffle(all_records)  # mix inaccurate records among valid ones

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    breakdown = Counter(kind for kind, _ in inaccurate)
    print(f"Generated {len(all_records)} records -> {args.output}")
    print(f"  valid:      {valid_count}")
    print(f"  inaccurate: {args.inaccurate}")
    for kind, n in sorted(breakdown.items()):
        print(f"    - {kind}: {n}")


if __name__ == "__main__":
    main()