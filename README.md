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
├── gen_dummy_json.py             # generates dummy data (valid + inaccurate records)
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
python gen_dummy_json.py --records 500 --inaccurate 40

# 3. Load it into PostgreSQL
python load_data.py --input output.json
```

Check that the container is `healthy` before step 3:

```bash
docker compose ps
```

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

