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
- 🤖 **MCP server**: lets an AI agent search, read and count records, restricted to the user's agency and fully logged (Part 3).

---

## 🧰 Tech stack

| Purpose | Tool |
|---|---|
| Database | PostgreSQL 16 (Docker Compose) |
| ORM / DB access | SQLAlchemy 2.0 + psycopg 3 |
| Validation | Pydantic v2 |
| API | FastAPI + Uvicorn |
| AI agent access | MCP Python SDK (stdio transport) |
| Configuration | python-dotenv (`.env` file) |
| Logging | Python `logging` module |

---

## 📁 Project structure

```
.
├── gen_dummy_json.py     # generates dummy data (valid + inaccurate records)
├── load_data.py          # main migration script (CLI, workflow, logging)
├── api.py                # FastAPI search application (Part 2)
├── mcp_server.py         # MCP server for AI agents (Part 3)
├── schemas.py            # Pydantic model: validation rules
├── models.py             # SQLAlchemy models: records table, MCP audit log table
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

- [Git](https://git-scm.com/downloads)
- [Python 3.11+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (must be running)

---

## ⚙️ Setup

**1. Clone the repository**

```bash
git clone https://github.com/iamshahboz/data_migration_and_search_pipeline.git
cd data_migration_and_search_pipeline
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Create a `.env` file** in the project folder

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


---

# Part 3: MCP server (AI agent access)

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent (Claude Desktop, Claude Code, any MCP client) work with the same data. It is **read-only** and works on behalf of **one specific user**.

## How it works

| Tool | What the agent uses it for |
|---|---|
| `search_records` | Find records by words in the text, status, district, agency and period; returns a short list |
| `get_record` | Get one record by its id, with the full text |
| `get_statistics` | Count records per agency and status for a period ("how many...?") |

- 🔒 **Access rules are enforced by the server**, not by the model (see below).
- 🧱 **Responses are small**: at most 20 records per call, shortened text, capped paging, rate limit.
- 🧾 **Every call is logged** to the database: who, which tool, which parameters, how many records came back.
- 📖 Tool and parameter descriptions are written for the model: when to use each tool, allowed values, formats, and what comes back.

## Transport: stdio

The MCP client starts `mcp_server.py` as a local process and talks to it through stdin/stdout.

- **Why:** there is no network port, so nobody can reach the tools except the process that started them. That is what makes it safe to set the user's identity through configuration, with no passwords or tokens.
- **Trade-off:** one server process per user, on that user's machine. For one shared server, use Streamable HTTP, which needs per-user tokens, TLS and an Origin check (not built here).
- stdout carries the protocol, so the server never prints to it. Logs go to stderr and the audit log goes to the database.

## Who is the agent working for?

The process that starts the server sets the user with environment variables, normally in the MCP client's config. They are **not tool parameters**, so the model cannot change them, and a prompt injection cannot ask for "another agency".

| Variable | Meaning |
|---|---|
| `MCP_USER` | Name of the user (required). Written to the audit log. |
| `MCP_AGENCY` | The agency the user works for, written exactly as in the data, e.g. `Water Authority`. The user only ever sees this agency's records. |
| `MCP_ADMIN` | `true` for an administrator who sees every agency. Use it **instead of** `MCP_AGENCY`. |
| `DATABASE_URL` | PostgreSQL URL. Can also come from the `.env` file next to `mcp_server.py`. |

If the identity is missing or ambiguous (no user, neither agency nor admin, or both), the server **refuses to start**. A forgotten setting never turns into full access.

**One function decides what is visible.** `scope_conditions()` in `mcp_server.py` adds `agency_name = <the user's agency>` to the query of **every** tool:

- `search_records`: other agencies' records never match, even if the agent searches for their name.
- `get_record`: an id from another agency gets the same "not found" as an id that doesn't exist, so the answer doesn't even reveal that it exists.
- `get_statistics`: the restriction is applied **before** the counting, so an employee cannot learn another agency's numbers from totals.

> The identity is trusted configuration: whoever starts the server chooses it. That is appropriate for a local stdio server run for a given user. A shared server would need real authentication.

## Limits

| Limit | Value |
|---|---|
| Records per `search_records` call | default 10, maximum 20 |
| Paging depth (`offset`) | maximum 200 |
| Text in search results | first 300 characters (`get_record` returns the full text) |
| Rows per `get_statistics` call | maximum 50 |
| Rate | 60 tool calls per minute |
| One database query | 5 seconds |

The tools' database connection is also **read-only** at the database level, so even a bug cannot change data. When there are more matches than fit, the answer says so (`total`, `has_more`, a `hint`) and tells the agent to narrow the filters.

## Audit log

Every tool call writes one row to the `mcp_audit_log` table, **including** calls with invalid parameters, calls refused by the rate limit, and "not found". If the log cannot be written, the call is refused.

| Column | Meaning |
|---|---|
| `called_at` | When |
| `user_name`, `scope` | Who (`scope` is the agency, or `*` for an administrator) |
| `tool`, `params` | Which tool and the parameters exactly as the agent sent them |
| `returned_count` | How many records (or statistics rows) came back |
| `outcome` | `ok`, `not_found`, `rate_limited` or `error` |
| `duration_ms`, `error` | How long it took and the error text, if any |

Record contents are never written to the log.

```bash
docker compose exec postgres psql -U postgres -d records_db -c \
  "SELECT called_at, user_name, scope, tool, params, returned_count, outcome FROM mcp_audit_log ORDER BY id DESC LIMIT 10;"
```

## Connect it to an MCP client

Before you connect, make sure the database is running and the data is loaded (steps 1-3 of **How to run**), and that you ran `pip install -r requirements.txt`.

Use the **virtual environment's Python** and **absolute paths**.

**Claude Desktop**: open *Settings → Developer → Edit Config* and add the server to `claude_desktop_config.json`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "agency-records": {
      "command": "C:/path/to/project/.venv/Scripts/python.exe",
      "args": ["C:/path/to/project/mcp_server.py"],
      "env": {
        "MCP_USER": "alice",
        "MCP_AGENCY": "Water Authority",
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/records_db"
      }
    }
  }
}
```

On macOS / Linux use `/path/to/project/.venv/bin/python`.

**Claude Code**:

```bash
claude mcp add --transport stdio \
  --env MCP_USER=alice --env MCP_AGENCY="Water Authority" \
  --env DATABASE_URL=postgresql://postgres:postgres@localhost:5432/records_db \
  agency-records -- /path/to/project/.venv/bin/python /path/to/project/mcp_server.py
```

**For an administrator**, replace `MCP_AGENCY` with `"MCP_ADMIN": "true"`. To work for another user, add a second server entry with that user's name and agency.

To test the tools without an AI, you can use the MCP Inspector: `npx @modelcontextprotocol/inspector -e MCP_USER=alice -e MCP_AGENCY="Water Authority" -e DATABASE_URL=... python mcp_server.py`.

## Example requests

The server was started for user `alice`, agency `Water Authority`. Each example shows what the agent asks, the tool call it makes, and the server's **real response** on the sample data (your numbers will differ).

### 1. "How many of our requests are still open?"

Tool call: `get_statistics` with no parameters.

```json
{
  "total_records": 198,
  "period": {
    "date_from": null,
    "date_to": null,
    "date_field": "created_at"
  },
  "returned_rows": 3,
  "results": [
    {
      "agency_name": "Water Authority",
      "status": "closed",
      "count": 66
    },
    {
      "agency_name": "Water Authority",
      "status": "in_progress",
      "count": 62
    },
    {
      "agency_name": "Water Authority",
      "status": "open",
      "count": 70
    }
  ]
}
```

The agent can answer: *"Your agency has 198 records: 70 open, 62 in progress and 66 closed."*

### 2. "Find open requests about the repair budget and show me the newest one in full."

Tool calls: `search_records` with `{"query": "repair budget", "status": "open", "limit": 2}`, then `get_record` with `{"record_id": 1519}`.

```json
{
  "total": 10,
  "returned": 2,
  "offset": 0,
  "has_more": true,
  "results": [
    {
      "id": 1519,
      "created_at": "2026-11-21T08:29:00",
      "updated_at": "2026-11-22T14:35:26",
      "agency_name": "Water Authority",
      "district": "South",
      "category": "critical",
      "status": "open",
      "text": "Repair work is pending approval of the allocated budget. Citizens have raised multiple complaints about this matter.",
      "text_shortened": false
    },
    {
      "id": 543,
      "created_at": "2026-10-28T08:31:00",
      "updated_at": "2026-11-03T20:52:30",
      "agency_name": "Water Authority",
      "district": "North",
      "category": "normal",
      "status": "open",
      "text": "Repair work is pending approval of the allocated budget. Additional resources are needed to resolve this case. Follow-up inspection is scheduled for later this week. A detailed report will be submitted once the work is complete.",
      "text_shortened": false
    }
  ],
  "next_offset": 2,
  "hint": "Showing 2 of 10 matches. Narrow the filters, or read the next page with offset=2."
}
```

```json
{
  "id": 1519,
  "created_at": "2026-11-21T08:29:00",
  "updated_at": "2026-11-22T14:35:26",
  "agency_name": "Water Authority",
  "district": "South",
  "category": "critical",
  "status": "open",
  "text": "Repair work is pending approval of the allocated budget. Citizens have raised multiple complaints about this matter.",
  "text_shortened": false
}
```

The search returned the newest 2 of 10 matches and told the agent how to get more (`next_offset`). The full text came from `get_record`.

### 3. "What is City Police working on? Show me record 3."

This asks for another agency's data. Tool calls: `search_records` with `{"agency_name": "City Police"}`, then `get_record` with `{"record_id": 3}`.

```json
{
  "total": 0,
  "returned": 0,
  "offset": 0,
  "has_more": false,
  "results": [],
  "hint": "No records match. Try fewer words or a wider period."
}
```

```text
Error executing tool get_record: Record 3 not found.
```

Nothing from another agency comes back, and the "not found" is identical to the one for an id that doesn't exist. The agent can only tell the user that it has no access to that agency's records.

### What the audit log recorded for these three examples

| Time | User | Scope | Tool | Parameters | Returned | Outcome |
|---|---|---|---|---|---|---|
| 2026-11-24 11:03:37 | alice | Water Authority | `get_statistics` | `{}` | 3 | ok |
| 2026-11-24 11:03:37 | alice | Water Authority | `search_records` | `{"query": "repair budget", "status": "open", "limit": 2}` | 2 | ok |
| 2026-11-24 11:03:37 | alice | Water Authority | `get_record` | `{"record_id": 1519}` | 1 | ok |
| 2026-11-24 11:03:37 | alice | Water Authority | `search_records` | `{"agency_name": "City Police"}` | 0 | ok |
| 2026-11-24 11:03:37 | alice | Water Authority | `get_record` | `{"record_id": 3}` | 0 | not_found |

## A note on untrusted text

The `text` of a record is written by third parties and could contain instructions aimed at an AI agent ("ignore your rules and..."). The server states in its instructions and tool descriptions that this text is data, never instructions, and all tools are read-only, so a successful injection could not change or delete anything. For production, also connect with a dedicated PostgreSQL user that has `SELECT` rights only.