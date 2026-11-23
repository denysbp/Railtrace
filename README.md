# Railtrace

Ingestion and analysis of metro trainset telemetry. It consists of four parts:

- **API** (FastAPI): receives reports and serves reads;
- **Worker**: applies the rules to each report;
- **PostgreSQL**: stores the data and serves as the queue between the API and the Worker;
- **frontend** (Next.js): the query pages.

```
backend/app/
  api/        HTTP routes (only translate requests and errors)
  services/   coordination: DB, transactions, locks
  domain/     rules as pure functions (standard library only)
  models/     SQLAlchemy tables and constraints
  schemas/    bodies and responses (Pydantic)
  worker.py   reports_raw queue consumer
  cli.py      `railtrace` command
backend/migrations/   Alembic
backend/tests/        unit/ (no DB) and integration/ (railtrace-test)
frontend/             Next.js (`web` service)
scripts/scenario.sh   automated scenario (steps 2–7 + checkpoints)
data/                 seed, batches, live stream and expected values
docs/                 schema.md and decisions/
```

## Requirements

- Docker with Docker Compose
- `make`
- [uv](https://docs.astral.sh/uv/) and Python 3.14: only for running the tests, the CLI or the API outside Docker
- Node 22: only for developing the frontend outside Docker

## How to run

```bash
make env       # creates .env with "change-me" values (if it doesn't already exist) — edit it
make           # = make up + make migrate
```

The `.env` needs, at a minimum, `DB_NAME`, `DB_USER`, `DB_PASSWORD` and `API_PORT`. Within compose, `DB_HOST` and `DB_URL` are defined by compose itself.

| Service | What it is | Address |
|---|---|---|
| `db` | PostgreSQL 17 | `localhost:${DB_PORT:-5432}` |
| `api` | FastAPI | http://localhost:8000, documentation at http://localhost:8000/docs |
| `worker` | Processes the report queue | only has logs (`make logs`) |
| `web` | Next.js frontend | http://localhost:3000 (`WEB_PORT` to change) |
| `cli` | `railtrace` command (`cli` profile, does not start with `up`) | `docker compose run --rm cli …` |

Other `Makefile` targets:

| Command | What it does |
|---|---|
| `make up` / `make down` / `make restart` | Starts, stops or restarts all services |
| `make migrate` | `alembic upgrade head` inside the `api` container |
| `make logs` / `make ps` | Logs and status of the services |
| `make live-stream` | Sends `data/live-stream.txt` to `POST /v1/reports`, one line per request |
| `make dev` | API in development mode, outside Docker (port 8000) |
| `make worker` | Worker outside Docker |
| `make clean` | Deletes Python and test caches |

Frontend outside Docker:

```bash
cd frontend && npm install && npm run dev    # http://localhost:3000, uses API_URL (defaults to http://localhost:8000)
```

### Endpoints

| Method | Path | |
|---|---|---|
| POST | `/v1/reports` | One report in `text/plain` (max. 1 KB) → `202` |
| POST | `/v1/depot/batches` | Depot file (`multipart`, max. 5 MB) → `202` |
| GET | `/v1/depot/batches/{id}` | Result of each line of the batch |
| GET | `/v1/lines` | Lines with their stations in order |
| GET | `/v1/duties?date=YYYY-MM-DD&line=` | Duties for a day |
| GET | `/v1/duties/{code}` | Duty and its assignments |
| GET | `/v1/duties/{code}/readings?metric=` | Values of a metric over time |
| GET | `/v1/duties/{code}/hourly?metric=` | Rollups by UTC hour |
| GET | `/v1/duties/{code}/summary` | Trainsets, measurements and summary by metric |
| GET | `/v1/duties/{code}/stations` | Stations of the line with the maximum axle value |
| POST | `/v1/duties/{code}/assignments` | New assignment (`409` if it overlaps another) |
| PATCH | `/v1/assignments/{id}` | Changes start/end (`409` if it overlaps another) |
| POST | `/v1/trainsets` | Registers a trainset |
| GET | `/v1/quarantine?reason=&limit=` | Reports in quarantine |
| GET | `/v1/stats` | Totals |

## Tests

```bash
uv run pytest backend/tests/unit        # domain only: no DB, ~0.2 s
uv run pytest backend/tests             # unit + integration
```

Integration tests run **only** on the `railtrace-test` database. `backend/tests/conftest.py` forces `DB_NAME=railtrace-test` and the suite refuses to run on another DB. Before each test, the tables are emptied and the seed is loaded again. If the DB is not accessible, the integration tests are skipped (`skip`).

To create the test database (once), with `db` running:

```bash
docker compose --env-file .env exec db sh -c 'createdb -U "$POSTGRES_USER" railtrace-test'
DB_NAME=railtrace-test DB_HOST=localhost uv run alembic upgrade head
```

## Scenario

```bash
make scenario        # = bash scripts/scenario.sh
```

The script runs against the API at `http://127.0.0.1:8000` (can be changed with `API=…`) and does the following, in order:

1. loads the seed (`railtrace seed`, see [decision 0002](docs/decisions/2-carregar-o-seed.md));
2. sends `depot-batch-01.txt`;
3. sends `live-stream.txt`, one line per request;
4. sends `depot-batch-02.txt`, waits for `pending = 0` and checks **checkpoint A** against `data/expected.json`;
5. removes TS-0003 from `VD-D03-20261103` at 08:40Z: first the `PATCH` to the end of TS-0003, then the one to the start of TS-0005;
6. registers TS-0099 on the VD line, creates the assignment in `VD-T01-20261104` and runs `replay-quarantine --reason unknown_trainset`;
7. waits for `pending = 0` and checks the **final checkpoint**.

Each value appears as `PASS`/`FAIL`, and at the end the script shows `SCENARIO: PASS` or `SCENARIO: FAIL (n wrong values)` (exit code 1).

**Must run on a clean DB.** Step 5 changes seed assignments. When re-running, step 1 tries to insert the original assignment again, which violates `ex_assignments_duty_no_overlap` (see [decision 0006](docs/decisions/6-r6-na-bd.md)). To start from scratch, delete the volume with `docker compose --env-file .env down -v && make`, or point the `.env` to another empty DB and run `make migrate`. **Warning:** `down -v` deletes all data.

## CLI

Inside Docker (the `cli` service mounts `./data` at `/app/data` read-only):

```bash
docker compose --env-file .env run --rm cli seed --file data/seed.json
docker compose --env-file .env run --rm cli replay-quarantine --reason unknown_trainset [--dry-run]
docker compose --env-file .env run --rm cli rebuild-read-models
```

Outside Docker, the same command (uses the `.env`, with `DB_HOST=localhost`): `uv run railtrace <command> …`.

| Command | What it does |
|---|---|
| `seed --file <json>` | Loads lines, stations, trainsets, duties and assignments. Idempotent for what has not been changed. |
| `replay-quarantine --reason <reason> [--dry-run]` | **R8**: re-applies the rules to reports in quarantine with that reason (e.g. after registering a trainset). With `--dry-run` it only shows what would change. Reasons: `malformed`, `bad_checksum`, `clock_invalid`, `unknown_trainset`, `unknown_station`, `unknown_metric`, `conflict`. |
| `rebuild-read-models` | **A4**: deletes revisions, measurements, results and rollups and reprocesses all reports in arrival order, in a single transaction. The Worker waits until it finishes. |

## Completed levels

[x] - "level 1"
[x] - "level 2"
[] - "level 3"

## Documentation

- [`docs/schema.md`](docs/schema.md): all tables, columns and constraints.
- [`docs/decisions/`](docs/decisions/): architecture decisions:
  - [1](docs/decisions/1-responsabilidade-dos-modelos.md) responsibility of each model
  - [2](docs/decisions/2-carregar-o-seed.md) loading the seed before the scenario
  - [3](docs/decisions/3-api-para-worker.md) how the API passes reports to the Worker
  - [4](docs/decisions/4-ordem-r3-r4.md) order independence in R3/R4
  - [5](docs/decisions/5-reatribuicao-e-rollups.md) reattribution and rollups after changing an assignment
  - [6](docs/decisions/6-r6-na-bd.md) R6 guaranteed by the DB
