# 0004 — Independence of arrival order in R3 and R4


## Context

Reports for the same measurement can arrive in any order: in real time, in a depot batch hours later, or mixing the two. The state of a measurement and conflict detection cannot depend on that order.

- **R3**: the state of a measurement results from the revisions applied in `rev` order. A number defines the metric, `-` removes it and an absent key keeps it. The station comes from the revision with the highest `rev`. Without metrics, the measurement does not appear.
- **R4**: reports with the same identity (`serial`, `measured_at`, `rev`) and different content are in conflict, and all of them go to quarantine with reason `conflict`.

## Decision

**Always store the revision.** Every valid report produces a row in `report_revisions`, even when it is a duplicate or enters conflict (`_apply_revision` in `services/process_report.py`). Thus, a report that arrives later always finds all earlier ones with the same identity, whatever their result was.

**R4: the decision looks at all revisions of the identity, not only the last one.** `classify_revision` (`domain/revisions.py`) receives the new content and that of all revisions already stored with the same identity:
- none → `NEW` (applied);
- all equal (same station, same metrics, values compared as `Decimal`, so `11.6 == 11.60`) → `DUPLICATE`;
- any different → `CONFLICT`. The new report **and all earlier ones with that identity**, including those already applied and duplicates, become `quarantined/conflict`;
- if the identity is already in conflict → `CONFLICT`, even if the new one is equal to one of the versions. A conflict is not undone.

Thus, the final set of states is the same for any order. For example, with A = A′ ≠ B:
- A, A′, B → A applied, A′ duplicate, then B causes a conflict and A and A′ become conflict;
- B, A, A′ → B applied, A causes a conflict (and B becomes conflict), A′ enters an identity already in conflict.

In both cases all three end up in `conflict`.

**R3: the measurement is recalculated from scratch on every change.** `_rebuild_measurement` reads all `applied` revisions of the measurement (`serial`, `measured_at`), across all `rev` values, and passes them to `apply_revisions` (`domain/revisions.py`), which **sorts them by `rev`** before applying them. The measurement is recalculated from the revisions, rather than applying only the latest on top of the previous state. Therefore, a `rev=1` revision arriving before `rev=0` gives the same result. When R4 removes revisions from `applied`, the measurement is recalculated without them and may return to the state of another `rev` or disappear.

## Alternatives considered

- **Apply each revision on top of the current measurement state**: the result would depend on the order (`rev=0` arriving after `rev=1` would erase more recent values) and there would be no way to undo a revision that later enters conflict.
- **Not storing duplicates or conflicts**: a third different report would not know that there had already been two versions, and the first applied one would never become conflict.
- **UNIQUE on `(trainset_id, measured_at, rev)`**: it would prevent storing the various versions of an identity, which is exactly what R4 needs to see (see [0001](1-responsabilidade-dos-modelos.md)).

## Consequences

- The effective state (measurement, quarantine due to conflict) does not depend on arrival order. This is covered by `tests/unit/test_revisions.py` and `tests/integration/test_process_report_r4.py`.
- **What depends on the order** is only *which* of two identical reports becomes `applied` and which becomes `duplicate` (R2: the first to arrive). The measurement content is the same in both cases. Therefore the Worker and `rebuild-read-models` process by increasing `id`, to give the same result.
- The guarantee assumes that reports of an identity are processed one at a time. With several Workers in parallel, two reports of the same identity could be classified at the same time without seeing each other. This is another reason for compose to start only one Worker (see [0003](3-api-para-worker.md)).
- Recalculating the measurement for each report costs one read of its revisions. There are few per measurement, so the cost is low.
