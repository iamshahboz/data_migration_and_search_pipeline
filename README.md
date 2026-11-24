# 🚚 Data Migration Pipeline

Generate dummy records (including deliberately broken ones), validate them, and migrate the good ones into **PostgreSQL**, safely and repeatably.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)

---

## ✨ Highlights

- 🐘 **PostgreSQL in Docker**: one command starts the database in the background.
- 🎲 **Dummy data generator**: choose the total number of records and how many of them are inaccurate.
- ✅ **Strict validation** with Pydantic: missing fields, wrong date formats, bad values and wrong dates order are all caught.
- 🛡️ **Bad data never stops the migration**: invalid and duplicate records are skipped and saved to a JSON file, each with the **reason** it was skipped.
- 🔁 **Safe to re-run**: running the loader again with the same input will **not create duplicate records**.
- ♻️ **Resumable**: if the migration stops for any reason, re-running it skips everything already stored and inserts only what's missing.
- 📝 **Full logging**: everything is written to the console and to `load.log`.
- ⏱️ **Timing built in**: the total migration time is logged at the end of every run.

---

## 🧰 Tech stack

| Purpose | Tool |
|---|---|
| Database | PostgreSQL 16 (Docker Compose) |
| ORM / DB access | SQLAlchemy 2.0 + psycopg 3 |
| Validation | Pydantic v2 |
| Configuration | python-dotenv (`.env` file) |
| Logging | Python `logging` module |

---

## 📁 Project structure

```
.
├── script.py             # generates dummy data (valid + inaccurate records)
├── load_data.py          # main migration script (CLI, workflow, logging)
├── schemas.py            # Pydantic model: validation rules
├── models.py             # SQLAlchemy model: database table definition
├── db.py                 # engine, table creation, batch insert
├── docker-compose.yml    # PostgreSQL container
├── requirements.txt      # Python dependencies
├── .env                  # your credentials (not committed)
│
├── output.json           # generated input data
├── skipped_records.json  # records skipped during migration (+ reason)
└── load.log              # log of every migration run
```

---

## ✅ Prerequisites

- [Python 3.11+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (must be running)

---

## ⚙️ Setup

**1. Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Create a `.env` file** in the project folder

```env
# Used by docker-compose.yml (database container)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=records_db

# Used by load_data.py (must match the values above)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/records_db
```

> The user, password and database name must be the same in both places. If your password has special characters (`@ # / : ?`), percent-encode them inside the URL.

---

## 🚀 Quick start

```bash
# 1. Start PostgreSQL in the background
docker compose up -d

# 2. Generate data: 500 records, 40 of them inaccurate
python script.py --records 500 --inaccurate 40

# 3. Load it into PostgreSQL
python load_data.py --input output.json
```

Check that the container is `healthy` before step 3:

```bash
docker compose ps
```

---

## 🎛️ Command options

### `script.py` (data generator)

| Flag | Description | Default |
|---|---|---|
| `--records` | Total number of records (valid + inaccurate) | required |
| `--inaccurate` | How many of those records should be inaccurate | `0` |
| `-o`, `--output` | Output JSON file | `output.json` |
| `--seed` | Random seed for reproducible data | none |

Inaccurate records are one of: **2–3 missing fields**, **wrong date format**, **same record with a different `updated_at`**, or an **exact duplicate**.

### `load_data.py` (migration)

| Flag | Description | Default |
|---|---|---|
| `--input` | Input JSON file | `output.json` |
| `--batch-size` | Records per insert transaction | `500` |
| `--skipped-file` | Where skipped records are saved | `skipped_records.json` |
| `--log-file` | Log file | `load.log` |
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `--database-url` | Overrides `DATABASE_URL` from `.env` | none |

---

## 🔍 How it works

```mermaid
flowchart LR
    A[output.json] --> B{Pydantic<br/>validation}
    B -- invalid --> S[skipped_records.json<br/>+ reason]
    B -- valid --> C{Duplicate or<br/>already in DB?}
    C -- yes --> S2[skipped / counted]
    C -- no --> D[(PostgreSQL<br/>batch insert)]
    D --> L[load.log]
    S --> L
    S2 --> L
```

1. Read the JSON file and log how many records were found.
2. Validate every record with Pydantic.
3. Skip duplicates (same `id` seen earlier in the file) and records whose `id` is already in the database.
4. Insert the remaining valid records in batches. Each batch is its own transaction, so a failed batch rolls back cleanly.
5. Save skipped records and print a summary with the total duration.

### Validation rules

- All fields are required: `id`, `created_at`, `updated_at`, `agency_name`, `district`, `category`, `status`, `text`
- Dates must use the format `YYYY-MM-DDTHH:MM:SS` (e.g. `2026-03-14T09:21:00`)
- `updated_at` cannot be earlier than `created_at`
- `category`: `normal`, `urgent` or `critical`
- `status`: `open`, `in_progress` or `closed`
- `agency_name` and `district`: up to 100 characters

---

## 🧾 Skipped records

Invalid records do **not** stop the migration. They are saved to `skipped_records.json` exactly as they were in the input, with one extra key: `reason`.

```json
{
  "id": 473,
  "created_at": "2026-07-15T21:36:44",
  "updated_at": "2026-10-26T03:03:45",
  "agency_name": "Housing Authority",
  "district": "South",
  "category": "critical",
  "reason": "missing field: status; missing field: text"
}
```

Possible reasons:

| Case | Example reason |
|---|---|
| Missing fields | `missing field: status; missing field: text` |
| Wrong date format | `bad date format: created_at` |
| Bad value | `invalid value: category` |
| Dates in wrong order | `updated_at is earlier than created_at` |
| Exact duplicate | `exact duplicate of record #50` |
| Same id, different data | `same id as record #8, differs in: updated_at` |

---

## 🔁 Re-running and recovery

- **Same input, run again:** no duplicates are created and the database is not changed. The log ends with `Data already migrated - nothing new to insert, database unchanged.`
- **Migration interrupted** (crash, closed terminal, Ctrl+C): run the same command again. Everything already stored is skipped and only the missing records are inserted.
- Records are matched by `id`. An existing `id` is never overwritten.

---

## 📝 Logging

All log lines go to the console **and** to `load.log` (new runs are appended). Example summary:

```
2026-11-24 13:13:28 | INFO | Total read:           500
2026-11-24 13:13:28 | INFO | Inserted:             460
2026-11-24 13:13:28 | INFO | Skipped:              40
2026-11-24 13:13:28 | INFO |   - validation:       17  (missing fields / bad dates / bad values)
2026-11-24 13:13:28 | INFO |   - duplicates:       23
2026-11-24 13:13:28 | INFO | Duration:             0.42s
```

Use `--log-level DEBUG` to also see the per-record "already in database" lines.

---

## ⏱️ How long does the migration take?

The total time is logged as `Duration` at the end of every run. Reference numbers (local PostgreSQL in a test environment, batch size 500, your machine will differ):

| Run | Records | Inserted | Duration |
|---|---|---|---|
| First load | 100,000 | 95,000 | ~9.5 s |
| Re-run, same file (nothing new) | 100,000 | 0 | ~2.3 s |

Tip: for very large files, a bigger batch (`--batch-size 2000`) means fewer log lines and fewer database round trips. The script reads the whole JSON file into memory, so a file with 500,000 records needs roughly 1 GB of RAM.

---

## 🔎 Check the data in the database

```bash
# Row count
docker compose exec postgres psql -U postgres -d records_db -c "SELECT count(*) FROM agency_records;"

# First rows
docker compose exec postgres psql -U postgres -d records_db -c "SELECT * FROM agency_records ORDER BY id LIMIT 5;"

# Table structure and constraints
docker compose exec postgres psql -U postgres -d records_db -c "\d agency_records"
```

You can also connect with DBeaver or pgAdmin using host `localhost`, port `5432` and the credentials from `.env`.

---

## 🛑 Stop and clean up

```bash
docker compose stop        # stop the database, keep the data
docker compose down        # remove the container, keep the data (volume)
docker compose down -v     # remove the container AND delete all data
```

---

## 🩺 Troubleshooting

| Problem | Fix |
|---|---|
| `no configuration file provided: not found` | The file must be named exactly `docker-compose.yml` (hyphen, not underscore) and be in the folder you run the command from. |
| `password authentication failed for user "postgres"` | The password in `DATABASE_URL` must match `POSTGRES_PASSWORD`. PostgreSQL only reads credentials when the volume is first created, so after changing them run `docker compose down -v` and start again. |
| Same error, credentials look correct | A local PostgreSQL may be using port 5432. Stop it, or map Docker to another port (`"5433:5432"`) and use `5433` in `DATABASE_URL`. |
| `connection refused` right after `up -d` | The database needs a few seconds. Wait until `docker compose ps` shows `healthy`. |
| `Could not read 'output.json'` | The input file doesn't exist. Generate it first with `script.py`, or pass the right path with `--input`. |