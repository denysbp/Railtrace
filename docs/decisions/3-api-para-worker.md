# 0003 — How the API passes reports to the Worker


## Context

Reports arrive in two ways: one at a time in real time (`POST /v1/reports`) or in a file from the depot (`POST /v1/depot/batches`). Processing a report involves validating (R1), applying revisions (R2–R4), assigning to a duty (R5) and updating rollups (R7). The API must respond quickly and must not lose reports, even if the Worker is stopped or fails midway.

## Decision

The `reports_raw` table is the queue. There is no broker (Redis, RabbitMQ…): the API and the Worker only share PostgreSQL.

**API (producer)**
- `POST /v1/reports` stores a row in `reports_raw` with the text exactly as it arrived, commits and responds with `202 Accepted` and the `report_id`. It does not interpret the report.
- `POST /v1/depot/batches` creates a `Batch` and one row in `reports_raw` per line of the file (ignoring empty lines and `#` comments), all in a single transaction (`services/ingest.py`). Responds `202` with the `batch_id`.
- `status` starts as `pending` and `received_at` is the time it was stored by the API. R1 uses that time for `clock_invalid`, not the time when the Worker processes the report.

**Worker (consumer)**, in `app/worker.py`:
- Requests the next `pending` report with an `id` greater than the last one seen, in `id` order (= arrival order), with `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1`.
- Processes it in a single transaction (`services/process_report.py`, A3): changes the `status` in `reports_raw`, stores `report_outcomes` (A2), the revisions, the measurement and the rollups, and commits once at the end.
- If there is a technical error, it rolls back and the report remains `pending`. The cursor advances anyway, so that a failing report does not block the following ones.
- When there is nothing left, the cursor returns to 0 (to retry the `pending` ones that failed) and the Worker waits 1 s before looking again.

**Coordination with other writes**: the Worker and `replay-quarantine` take a shared lock (`pg_advisory_xact_lock_shared`, `services/locks.py`). `rebuild-read-models` (A4) takes the same lock in exclusive mode, so processing waits while a rebuild runs. API ingestion does not use this lock and is never blocked.

## Alternatives considered
- **Message broker**: one more service to run and maintain. There would be two sources of truth (queue and DB), and it would be necessary to ensure that storing in the DB and publishing the message happen together. With the queue in the DB, storing the report *is* putting it in the queue.


## Consequences

- An accepted report (`202`) is never lost: it stays in `reports_raw` until processed, even if the Worker is down.
- `pending` in `/v1/stats` and in `/v1/depot/batches/{id}` = received − processed. The scenario waits for `pending = 0` before checking the values.
- The latency between receiving and processing a report is up to ~1 s when the queue is empty.
- `SKIP LOCKED` allows multiple Workers without processing the same report. Even so, compose starts only one, because arrival order matters for R2 (see [0004](4-ordem-r3-r4.md)).
- A report that always fails due to a technical error is retried on each pass. The error appears in the Worker log.
