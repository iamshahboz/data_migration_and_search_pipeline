# 🚚 Data Migration Pipeline

Generate dummy records (including deliberately broken ones), validate them, and migrate the good ones into **PostgreSQL**, safely and repeatably. Then search the data through a **FastAPI** application (see [Part 2](#part-2-search-api-fastapi)).

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)

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
- 🔌 **Search API**: filter the migrated data by agency, district, status and period (Part 2).

---

## 🧰 Tech stack

| Purpose | Tool |
|---|---|
| Database | PostgreSQL 16 (Docker Compose) |
| ORM / DB access | SQLAlchemy 2.0 + psycopg 3 |
| Validation | Pydantic v2 |
| API | FastAPI + Uvicorn |
| Configuration | python-dotenv (`.env` file) |
| Logging | Python `logging` module |

---

## 📁 Project structure

```
.
├── gen_dummy_json.py     # generates dummy data (valid + inaccurate records)
├── load_data.py          # main migration script (CLI, workflow, logging)
├── api.py                # FastAPI search application (Part 2)
├── schemas.py            # Pydantic model: validation rules
├── models.py             # SQLAlchemy model: database table definition
├── db.py                 # engine, table creation, batch insert
├── docker-compose.yml    # PostgreSQL + API containers
├── Dockerfile            # image for the API
├── .dockerignore         # files kept out of the API image
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

# Used by load_data.py and api.py when run on your machine (must match the values above)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/records_db
```

> The user, password and database name must be the same in both places. If your password has special characters (`@ # / : ?`), percent-encode them inside the URL.

---

## 🚀 How to run

Run these commands in order, from the project folder, with your virtual environment active and your `.env` file created (see **Setup** above).

```bash
# 1. Start PostgreSQL in the background
docker compose up -d postgres

# 2. Generate data: 500 records, 40 of them inaccurate
python gen_dummy_json.py --records 500 --inaccurate 40

# 3. Load it into PostgreSQL
python load_data.py --input output.json

# 4. Start the API (builds the image on the first run)
docker compose up -d --build
```

- Before step 3, check that the database container is `healthy`: `docker compose ps`
- Once step 4 is done, the API is at http://127.0.0.1:8000/records and the interactive docs are at http://127.0.0.1:8000/docs
- Running step 3 again with the same file is safe: no duplicates are created.
- Developing the API? Use `uvicorn api:app --reload` instead of step 4 for auto-reload.

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
docker compose stop        # stop the containers, keep the data
docker compose down        # remove the containers, keep the data (volume)
docker compose down -v     # remove the containers AND delete all data
```

---

# Part 2: Search API (FastAPI)

A small read-only API on top of the migrated data. It connects to the same PostgreSQL database and lets you search and filter records. (To start it, see [How to run](#-how-to-run).)

## How it works

| Endpoint | What it does |
|---|---|
| `GET /records` | Returns records, filtered by **agency name**, **district**, **status** and **period** (one filter or any combination) |
| `GET /search` | Text search in the `text` field |
| `GET /statistics` | Number of records per **agency name and status** for a period |

- 🔓 `/records` with no parameters simply returns the first **50** records.
- 🧱 Every endpoint returns at most **50 results** per request. Use `offset` to page through the rest.
- 📊 Every response includes `total`: the number of matches (or of agency/status rows for `/statistics`) before the limit is applied.
- 📖 Interactive documentation is built in at `/docs`.

## Using `/records` (filters)

All parameters are optional and can be combined.

| Parameter | Meaning | Example |
|---|---|---|
| `agency_name` | Case-insensitive, partial match | `agency_name=water` |
| `district` | Case-insensitive, partial match | `district=north` |
| `status` | Exact: `open`, `in_progress` or `closed` | `status=open` |
| `date_from` | Period start, inclusive (`YYYY-MM-DD`) | `date_from=2026-03-01` |
| `date_to` | Period end, inclusive (`YYYY-MM-DD`) | `date_to=2026-03-31` |
| `date_field` | Date the period applies to: `created_at` (default) or `updated_at` | `date_field=updated_at` |
| `limit` | Records per response (default and maximum: 50) | `limit=20` |
| `offset` | Skip this many records, for paging | `offset=40` |

**Examples**

```
# Everything (first 50 records)
http://127.0.0.1:8000/records

# One filter
http://127.0.0.1:8000/records?status=open

# Combination of filters
http://127.0.0.1:8000/records?agency_name=water&district=north&status=closed

# Period (created in March 2026)
http://127.0.0.1:8000/records?date_from=2026-03-01&date_to=2026-03-31

# Period on updated_at, combined with a status
http://127.0.0.1:8000/records?date_from=2026-06-01&date_to=2026-06-30&date_field=updated_at&status=in_progress

# Paging: records 41-60
http://127.0.0.1:8000/records?limit=20&offset=40
```

Or from the command line:

```bash
curl "http://127.0.0.1:8000/records?status=open&district=north"
```

**Response**

```json
{
  "total": 8064,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": 1,
      "created_at": "2026-06-12T03:58:23",
      "updated_at": "2026-10-16T13:32:51",
      "agency_name": "Public Works Department",
      "district": "North",
      "category": "critical",
      "status": "open",
      "text": "A detailed report will be submitted once the work is complete."
    }
  ]
}
```

Invalid input returns a `422` error with an explanation, for example `limit` above 50, an unknown `status`, or `date_from` later than `date_to`.

## Using `/search` (text search)

Searches the `text` field. Matching is case-insensitive and **all words must appear, in any order**.

| Parameter | Meaning | Example |
|---|---|---|
| `q` | Words to look for (required) | `q=repair budget` |
| `limit` | Results per response (default and maximum: 50) | `limit=20` |
| `offset` | Skip this many results, for paging | `offset=20` |

```
http://127.0.0.1:8000/search?q=repair budget
http://127.0.0.1:8000/search?q=inspection&limit=20&offset=20
```

The response has the same shape as `/records` (`total`, `limit`, `offset`, `results`). A missing or empty `q` returns a `422` error.

## Using `/statistics`

Counts records per `agency_name` and `status`, for a period. Without a period it counts all records.

| Parameter | Meaning | Example |
|---|---|---|
| `date_from` | Period start, inclusive (`YYYY-MM-DD`) | `date_from=2026-03-01` |
| `date_to` | Period end, inclusive (`YYYY-MM-DD`) | `date_to=2026-03-31` |
| `date_field` | Date the period applies to: `created_at` (default) or `updated_at` | `date_field=updated_at` |
| `limit` | Rows per response (default and maximum: 50) | `limit=10` |
| `offset` | Skip this many rows, for paging | `offset=10` |

```
http://127.0.0.1:8000/statistics
http://127.0.0.1:8000/statistics?date_from=2026-03-01&date_to=2026-03-31
```

```json
{
  "total": 30,
  "limit": 50,
  "offset": 0,
  "results": [
    { "agency_name": "City Police", "status": "closed", "count": 284 },
    { "agency_name": "City Police", "status": "in_progress", "count": 271 },
    { "agency_name": "City Police", "status": "open", "count": 241 }
  ]
}
```

Rows are sorted by agency name, then status. Here `total` is the number of agency/status rows for the period (30 = 10 agencies x 3 statuses).