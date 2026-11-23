# 0001 — Responsibility of each model


## Context

The SQLAlchemy models live in `backend/app/models/` and are all registered in `app/models/__init__.py` so that they appear in `Base.metadata` (Alembic and relationships). This document defines what each model represents, who writes it and what is **not** its responsibility.

Models only store data and ensure its integrity (FKs, UNIQUE, CHECK, exclusion constraints). They do not contain business rules: those live in `domain/` (pure functions) and `services/` (coordination and DB access).

## Decision

### Reference data

Loaded by the `railtrace seed` command (`services/seed.py`), idempotently.

| Model | Table | Responsibility |
|---|---|---|
| `Line` | `lines` | Metro line, identified by the unique `code` (e.g. `AZ`). |
| `Station` | `stations` | Physical station, identified by the unique `code` (e.g. `SSE`). An interchange station exists only once. |
| `LineStation` | `line_stations` | Links stations to lines and stores the `position` of each station on the route. Allows a station to belong to several lines. `UNIQUE(line_id, position)`. |
| `Trainset` | `trainsets` | Trainset, identified by the unique `serial` (e.g. `TS-0001`), with its line (`home_line_id`). |
| `Duty` | `duties` | Planned service on a line, with planned start and end (`planned_end > planned_start`). |
| `Assignment` | `assignments` | Links a trainset to a duty during an interval `[started_at, ended_at)`. Two exclusion constraints (GiST, `btree_gist` extension) prevent a trainset from being in two duties at the same time and a duty from having two trainsets at the same time. Also written by the API (`POST /duties/{code}/assignments`, `PATCH /assignments/{id}`). |

### Ingestion

Written by the API. The API only stores what it receives; it does not interpret reports.

| Model | Table | Responsibility |
|---|---|---|
| `Batch` | `batches` | File sent by the depot (`POST /depot/batches`). Groups the reports from that file. |
| `ReportRaw` | `reports_raw` | Report as it was received, append-only: `raw_content` is never changed. Stores the origin (`batch_id` and `batch_line`, or NULL when it came in real time via `POST /reports`) and the processing result (`status` and, when quarantined, `quarantine_reason`). |

`ReportRaw` has no interpreted fields (trainset, instant, metrics): those only exist after processing, in `ReportRevision`.

### Telemetry

Written by the Worker (not yet implemented).

| Model | Table | Responsibility |
|---|---|---|
| `ReportRevision` | `report_revisions` | Valid report already interpreted: trainset, `measured_at`, `rev` (≥ 0) and station. Each `ReportRaw` produces at most one revision (unique `report_raw_id`). |
| `ReportRevisionMetric` | `report_revision_metrics` | Metric values received in a revision, one row per metric. PK `(report_revision_id, metric)`. |
| `Measurement` | `measurements` | Effective state of a measurement after valid revisions have been applied. One per trainset and instant (`UNIQUE(trainset_id, measured_at)`). Stores the assignment to a duty (`duty_id`, NULL when unassigned). |
| `MeasurementMetric` | `measurement_metrics` | Effective metric values of a measurement. PK `(measurement_id, metric)`. |

### Read models for the read endpoints (A2)

Written by the Worker in the same transaction in which it processes each report. The read endpoints only read these tables (and `measurements`).

| Model | Table | Responsibility |
|---|---|---|
| `ReportOutcome` | `report_outcomes` | Result of each already processed report: `status`, `quarantine_reason`, origin (`batch_id`, `batch_line`), original line and arrival time. Updated when R4 puts earlier reports in conflict. A report with no row here is still pending processing. Read by `/depot/batches/{id}`, `/quarantine` and `/stats`. |
| `DutyHourlyRollup` | `duty_hourly_rollups` | R7: per duty, metric and UTC hour, `count`, `value` and `coverage`. |
| `DutyMetricSummary` | `duty_metric_summaries` | R7: per duty and metric, the value over the whole duty. |
| `DutyStationStats` | `duty_station_stats` | R7: per duty and station, the number of reports and the largest `AX*` value. |

### Enums (`models/enums.py`)

- `ReportStatus`: `pending`, `applied`, `duplicate`, `quarantined`.
- `QuarantineReason`: `malformed`, `bad_checksum`, `clock_invalid`, `unknown_trainset`, `unknown_station`, `unknown_metric`, `conflict`. `conflict` is only a quarantine reason, not a status.

The DB stores the value (`'pending'`), not the member name (`values_callable`).

## Alternatives considered

- **Metrics as columns** (`spd`, `kwh`, `ax1`…) in `report_revisions` and `measurements`: a new metric would require changing the tables. With one row per metric, a new metric does not change the schema.
- **UNIQUE on `(trainset_id, measured_at, rev)`** in `report_revisions`: it would prevent storing different reports with the same identity, which R4 requires in order to detect conflicts. Only a non-unique index remains on those columns.
- **Mandatory `station_id`**: most reports in the sample data have no station (`-`). Therefore `station_id` accepts NULL in `report_revisions` and `measurements`.

## Consequences

- Clear separation between what was **received** (`ReportRaw`), what was **interpreted** (`ReportRevision`) and the **effective state** (`Measurement`). The read models can be rebuilt from the revisions without touching the original reports.
- A `ReportRaw` with a revision cannot be deleted (FK `RESTRICT`), which maintains append-only.
- Metrics are deleted with the revision or measurement they belong to (`ON DELETE CASCADE`).
- Values use `Numeric` without fixed precision (read as `Decimal`), to store the value exactly as it was received. `value` accepts NULL, to represent the removal of a metric (R3).
- No constraint guarantees that metrics are known or that `duty_id` is consistent with assignments: those are Worker rules.
- `Measurement` does not store which revision produced it.
