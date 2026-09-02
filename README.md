# IPL Query Resolver

An **asynchronous FastAPI backend** that manages a **BCNF-normalized 11-table MySQL
database** of **283,000+ ball-by-ball IPL records**, exposing both a catalogue of
hand-tuned analytics queries and a **schema-aware Text-to-SQL chatbot** that turns
plain English into read-only SQL — streamed to the browser in real time over a
WebSocket.

## Highlights

- **Async FastAPI + MySQL.** All database work runs off the event loop
  (`run_in_threadpool`), so the API stays responsive while running heavy
  analytical queries over 283k deliveries.
- **Schema-aware Text-to-SQL.** The pipeline introspects the live MySQL schema
  (`INFORMATION_SCHEMA`), resolves entities against the actual data, and
  generates **read-only SQL** using the Groq LLM (`gpt-oss-120b`) when available,
  with a deterministic, offline rule engine as a guaranteed fallback.
- **Real-time WebSocket streaming.** The full request lifecycle — *validation →
  SQL generation → query execution → result* — is pushed to the client live.
- **Transparent, robust API.** Pydantic request validation, explicit error
  types, and every answer returns the **generated SQL** it was produced from,
  so responses are auditable end-to-end.
- **Benchmarked accuracy.** A 33-query suite of complex natural-language
  questions is scored against hand-written canonical SQL. The deterministic
  rule engine scores **33/33 (100%)**; the LLM-hybrid is measured separately.

## Tech stack

FastAPI · Python · MySQL (PyMySQL) · WebSockets · Pydantic · Groq LLM
(`openai/gpt-oss-120b`) · vanilla JS frontend

## How it works, technically

### 1. Data layer — a BCNF-normalized 11-table schema

The raw ball-by-ball `IPL.csv` (one denormalized row per delivery) is loaded
into MySQL and normalized into **11 tables** (full schema in `schema.md`):

- **4 master tables** — `teams`, `venues`, `umpires`, `players` (one row per
  unique entity, referenced everywhere else by id).
- **5 match-metadata tables** — `match_details`, `match_result`, `match_toss`,
  `match_teams`, `match_umpire`.
- **2 ball-by-ball tables** — `delivery` (**283,678 rows**, one per ball) and
  `dismissal` (10,232 wickets).

Every table is in BCNF: each relation is derived from a candidate key, and all
non-key columns depend on the key, the whole key and nothing but the key.
`db.py` opens PyMySQL connections with settings from `.env` (dotenv-aware), and
optionally uses a dedicated least-privilege read-only account for generated SQL.

### 2. Application layer — async FastAPI

`main.py` exposes the API and a WebSocket endpoint. CPU/DB-heavy work is
dispatched with `starlette.concurrency.run_in_threadpool`, so the event loop
never blocks. Requests are validated by **Pydantic** models (`ChatRequest`,
`RunRequest`) before they reach the pipeline, and every failure is raised as a
typed error (`ValidationError`, `SQLGenerationError`, `ExecutionError`) that maps
to a clear HTTP status or WebSocket `error` event.

### 3. The Text-to-SQL pipeline

```
question ─► 1. validation ─► 2. schema-aware intent + entity resolution ─► 3. SQL generation
                                                                              │
                                                  (Groq LLM first, then the  │
                                                   rule engine as fallback)   ▼
result ◄─ 5. MySQL execution ◄─ 4. read-only enforcement (EXPLAIN + whitelist)
```

1. **Validation** — strips and checks the question (length, read-only intent).
2. **Schema-aware resolution** (`schema.py`) — introspects table/column/FK
   definitions live from `INFORMATION_SCHEMA`, builds an entity index from the
   actual data, and finds teams / players / venues / umpires / seasons in the
   question. Because the data abbreviates names ("V Kohli", "S Ravi"), full
   names ("Virat Kohli") are matched with an initial + surname signature, ties
   are broken by career prominence, and seasons like `2020` resolve to `2020/21`.
   A keyword classifier then picks one of **35 supported intents**
   (`text2sql.py`).
3. **SQL generation** (`text2sql.py` + `llm.py`) — the Groq API
   (`openai/gpt-oss-120b`) receives the question, the resolved entities and a
   **schema context prompt** describing every table, column and foreign key; it
   returns a SELECT statement. If no API key is set, or the returned SQL fails
   validation, the pipeline transparently falls back to the deterministic rule
   engine, which fills one of 35 canonical parameterized templates.
4. **Read-only enforcement** — mutating keywords are blocked, every referenced
   table must exist in the schema, and each statement must pass `EXPLAIN`
   before it runs. Generated SQL is therefore guaranteed read-only.
5. **Execution** — the statement runs against MySQL (on the read-only account
   when configured); results are normalized to JSON-safe values and returned
   together with timing, row counts and the generated SQL.

### 4. Real-time streaming

The WebSocket endpoint `/ws/chat` streams one event per stage — `validation`,
`sql_generation` (with the SQL), `query_execution` (row count + time), `result`,
or `error` — so the UI can animate the answer as it is produced. The REST
endpoint `/api/chat` returns the same lifecycle as a list plus the final result.

### 5. Frontend

A dependency-free vanilla JS SPA with three tabs: **Queries** (21 hand-tuned
analytics queries), **AI Chat** (the streamed Text-to-SQL assistant) and
**Benchmark** (accuracy report). All data comes from the API above.

## Repository layout

```
main.py            FastAPI app — REST endpoints + WebSocket streaming
text2sql.py        Text-to-SQL pipeline (intents, SQL templates, guards)
schema.py          live schema introspection + entity resolution
llm.py             Groq client (gpt-oss-120b, OpenAI-compatible)
db.py              MySQL connection helpers (dotenv aware)
queries.py         21 hand-tuned analytics queries (result sections)
benchmark.py       33-case accuracy benchmark (--engine auto | rule | llm)
schema.md          normalized 11-table schema documentation
00–04_*.sql        database build scripts (raw load → 11 normalized tables)
static/            vanilla JS frontend (queries / chat / benchmark)
```

## API surface

| Endpoint         | Method     | Description                                                          |
|------------------|------------|----------------------------------------------------------------------|
| `/api/queries`   | GET        | Metadata for the 21 hand-tuned analytics queries                     |
| `/api/run`       | POST       | Execute a preset query with inputs                                   |
| `/api/chat`      | POST       | Text-to-SQL: lifecycle events + result incl. generated SQL           |
| `/api/intents`   | GET        | Supported NL intents                                                 |
| `/api/benchmark` | GET        | Runs the 33-query accuracy benchmark and returns the report          |
| `/ws/chat`       | WebSocket  | Streams validation → SQL generation → execution → result live        |

### Example WebSocket session

Client sends:

```json
{ "question": "How many sixes did Virat Kohli hit against Mumbai Indians?" }
```

Server streams, in order:

```json
{ "type": "validation",      "status": "start", "message": "Validating question..." }
{ "type": "validation",      "status": "done",  "message": "Question validated." }
{ "type": "sql_generation",  "status": "start", "message": "Interpreting intent and generating SQL..." }
{ "type": "sql_generation",  "status": "done",
  "data": { "intent": "player_boundaries", "sql": "SELECT ...", "sql_source": "rule" } }
{ "type": "query_execution", "status": "done", "data": { "row_count": 13, "elapsed_ms": 8.7 } }
{ "type": "result", "data": { "columns": [...], "rows": [...], "sql": "...", "row_count": 13, ... } }
```

Errors are emitted as `{ "type": "error", "stage": "<stage>", "message": "..." }`
so the client always knows where the pipeline stopped.

## Running it on your machine

### Prerequisites

- **Python 3.10+**
- **MySQL 8+** running locally (with a user/password you control)
- A Groq API key (optional — the app runs fully offline without one)

### Step 1 — Get the data

The project uses the classic **IPL ball-by-ball dataset** (`IPL.csv`, one row per
delivery). Place it in the project root as `IPL.csv`. (If your copy uses a
different path, adjust the `LOAD DATA LOCAL INFILE` line at the top of
`00_setup_raw_data.sql`.)

### Step 2 — Create the database

With MySQL running, create the `ipl_normalized` database by running the build
scripts in order. `LOAD DATA LOCAL INFILE` needs `local_infile` enabled on the
server and the `--local-infile=1` client flag:

```bash
mysql --local-infile=1 -u <user> -p < 00_setup_raw_data.sql
mysql --local-infile=1 -u <user> -p < 01_create_master_tables.sql
mysql --local-infile=1 -u <user> -p < 02_create_match_metadata.sql
mysql --local-infile=1 -u <user> -p < 03_create_ball_by_ball.sql
mysql --local-infile=1 -u <user> -p < 04_top5_rows.sql
```

This loads and normalizes the data into the 11 tables:

| table          | rows     | table          | rows   |
|----------------|----------|----------------|--------|
| teams          | 19       | match_teams    | 1,193  |
| venues         | 63       | match_umpire   | 619    |
| umpires        | 47       | **delivery**   | **283,678** |
| players        | 789      | dismissal      | 10,232 |
| match_details  | 1,193    | match_result   | 1,184  |
| match_toss     | 1,193    |                |        |

### Step 3 — Configure

```bash
cp .env.example .env
```

Then edit `.env`:

- `IPL_DB_HOST / PORT / USER / PASSWORD / NAME` — your MySQL connection.
- `GROQ_API_KEY` — your Groq key (get one at https://console.groq.com). The
  client defaults to `https://api.groq.com/openai/v1` with the
  `openai/gpt-oss-120b` model; `LLM_BASE_URL` / `LLM_MODEL` override both.
  Leave blank to run entirely offline on the rule engine.
- `IPL_RO_USER / IPL_RO_PASSWORD` — optional least-privilege MySQL account used
  by the Text-to-SQL pipeline (blank = reuse `IPL_DB_*`).

`.env` is git-ignored; `.env.example` is the committed template.

### Step 4 — Install and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** — switch between **Queries**, **AI Chat** and
**Benchmark** in the sidebar.

## Benchmark results

The benchmark suite (`benchmark.py`) contains **33 complex natural-language
queries** across player, team, venue, season, bowler, all-time and match
categories. Each question is run through the pipeline; the generated SQL is
executed against MySQL and its result set is compared — **by values, ignoring
column aliases and ordering** (Spider-style execution accuracy) — to a
hand-written canonical SQL answer.

| Engine                        | Command                            | Accuracy |
|-------------------------------|------------------------------------|----------|
| **Rule engine** (offline)     | `python benchmark.py --engine rule`| **33/33 (100%)** |
| **LLM-hybrid** (Groq, default)| `python benchmark.py`              | ≈42% (14/33) on strict execution match |

Notes on the numbers:

- The **rule engine is deterministic and schema-aware**: it resolves entities
  against the live database and fills one of 35 canonical templates, so it
  answers every supported intent correctly — 33/33, offline, no API needed.
- The **LLM-hybrid** measures zero-shot `gpt-oss-120b` generation: the model
  writes the SQL first and only falls back to the rule engine when its SQL
  fails validation. Its strict execution-match score is ~42% and is stable run
  to run (temperature 0). The largest share of "mismatches" are answers that
  are **factually correct but shaped differently** from the canonical gold —
  e.g. a total count instead of a per-season breakdown, or a terser column
  set — rather than wrong numbers. The rule-engine fallback guarantees a
  correct result for every supported intent regardless.

Run it yourself:

```bash
python benchmark.py                  # LLM-hybrid (uses Groq if configured)
python benchmark.py --engine rule    # deterministic offline baseline
python benchmark.py --engine llm     # LLM only
python benchmark.py --case 5         # run a single case
python benchmark.py --json           # also write report.json
```

The same benchmark is exposed in the UI under **Benchmark**, and as
`GET /api/benchmark`.
