# 0006 — R6 guaranteed by the database


## Context

R6 (assignments): a trainset cannot be in two duties at the same time, and a duty cannot have two trainsets at the same time. The ranges are `[started_at, ended_at)`, so an assignment ending at 08:40 and another starting at 08:40 do not overlap.

Assignments are written by three different paths: the seed, `POST /v1/duties/{code}/assignments` and `PATCH /v1/assignments/{id}`. There may be concurrent requests.

## Decision

The rule lives in the schema, with two GiST **exclusion constraints** on `assignments` (`models/assignment.py`, migration `da18af22626b`):

```sql
EXCLUDE USING gist (trainset_id WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)  -- ex_assignments_trainset_no_overlap
EXCLUDE USING gist (duty_id     WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)  -- ex_assignments_duty_no_overlap
```

- `tstzrange(…, '[)')` represents the range with the start inclusive and the end exclusive, the same as in R5 (`AssignmentPeriod.covers`).
- `&&` = "the ranges overlap". Together with `=` on the trainset (or duty), the DB rejects two rows with the same trainset (or duty) and overlapping ranges.
- The `btree_gist` extension (created in the migration) allows using `=` on integers in a GiST index.
- `CHECK (ended_at > started_at)` (`ck_assignments_interval`) prevents empty or inverted ranges.

The service does not check for overlaps before writing. It performs `flush` and translates the DB error (`_flush_or_overlap` in `services/assignments.py`): `ExclusionViolation` becomes `AssignmentOverlapError`, which the API returns as `409 Conflict` ("Assignment overlaps an existing one"). The frontend displays that message as received.

## Alternatives considered

- **Check in code with a `SELECT` before `INSERT`/`UPDATE`**: two concurrent requests could both pass the check and store overlapping assignments. To avoid that, it would be necessary to lock tables or use `SERIALIZABLE`. The constraint is atomic and does not depend on who writes.
- **Check in code and in the DB**: it would duplicate the rule in two places that could diverge (for example on end inclusivity), with no benefit. The DB is the only source of the rule.
- **Trigger**: does the same as the exclusion constraint, with more code and no index.

## Consequences

- No write path (API, seed, manual SQL) can store overlapping assignments.
- The `PATCH` of step 5 must be done in order: first shorten the end of TS-0003, then bring forward the start of TS-0005. In the reverse order, the two would overlap for a moment and the DB would reject the request.
- **What the DB does not guarantee**: that the trainset belongs to the same line as the duty. This is checked in the service (`TrainsetWrongLineError` → `422`), because it would require comparing with other tables, which a constraint cannot do.
- The seed only ignores an assignment that already exists **exactly as is** (`_insert_assignments` in `services/seed.py`). If a seed assignment has been changed (for example by step 5 of the scenario), reloading the seed tries to insert it again, and the constraint rejects it with `ExclusionViolation`. Therefore the scenario must run on a clean DB.
