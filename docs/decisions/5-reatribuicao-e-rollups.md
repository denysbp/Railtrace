# 0005 — Reattribution and rollups after changing an assignment


## Context

- **R5**: a measurement belongs to the duty of its trainset's assignment that covers `measured_at`, with the start inclusive and the end exclusive (`[started_at, ended_at)`). With no assignment covering it, it is unassigned (`duty_id = NULL`).
- **R7**: per duty, the hourly rollups, the duty summary and the station statistics (`duty_hourly_rollups`, `duty_metric_summaries`, `duty_station_stats`).

Assignments change after measurements already exist: `POST /v1/duties/{code}/assignments` creates one, and `PATCH /v1/assignments/{id}` changes the start or end (step 5 of the scenario). The already stored measurements and the rollups of the duties involved must follow the change.

## Decision

**Reattribution is done in the same transaction as the assignment change** (`services/assignments.py`):
1. The assignment is created or changed and sent to the DB with `flush`. The exclusion constraints validate it already here (see [0006](6-r6-na-bd.md)).
2. `reattribute_measurements` (`services/attribution.py`) reads all assignments of the trainset and the measurements of that trainset in the affected range:
   - **create**: the range of the new assignment;
   - **change**: from the earliest to the latest of the old and new dates (`min(old start, new start)` to `max(old end, new end)`), to capture measurements that enter and those that leave.
3. For each measurement, `find_duty` (`domain/attribution.py`) decides the duty. Only those that change are written.
4. Rollups are recalculated **for all duties that measurements left and entered** (`refresh_rollups` in `services/rollups.py`).
5. A single commit at the end: the assignment, the measurements and the rollups change together or nothing changes.

**A duty's rollups are always recalculated from scratch** (`_recompute_duty`): it deletes the rows for that duty in the three tables, reads all measurements assigned to the duty and recalculates using the pure functions in `domain/aggregation.py`. There are no incremental updates (adding or subtracting a value). Before that, the duty row is locked (`SELECT … FOR UPDATE`) so that two recalculations of the same duty do not overlap.

The same `refresh_rollups` is used by the Worker: when a measurement is created, changed or deleted, the old duty and the new duty are recalculated (`_rebuild_measurement`). In `rebuild-read-models` (A4), recalculations are deferred (`defer_rollups`) and each duty is calculated only once at the end.

## Alternatives considered

- **Reattribute all measurements of the trainset**: it would give the same result, but reads measurements outside the range that cannot change.

## Consequences

- After the `PATCH` responds, `/summary`, `/hourly`, `/stations` and `/readings` already reflect the new assignment. This is what the scenario's final checkpoint checks.
- The cost of recalculating a duty is proportional to the number of measurements in that duty (a duty lasts 4 h, ~48 measurements per trainset).
- **Known limitation**: the Worker and an assignment change share no lock. Imagine the Worker is creating a measurement for a trainset at the same time as an assignment for that trainset is changed. The Worker may have read the old assignments, and the reattribution may not see the measurement yet to be stored. In that case, the measurement stays in the old duty until it is processed again (for example with `railtrace rebuild-read-models`). In the scenario this does not happen, because step 5 only runs after `pending = 0`.
