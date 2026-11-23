# 0002 — Loading the seed before the scenario


## Context

The scenario asks to run steps 2–7 (`scripts/scenario.sh` / `make scenario`) on a freshly started system. The subject does not say whether the seed (`data/seed.json`) has to be loaded beforehand or not.

On a freshly started system, the reference tables (`lines`, `stations`, `line_stations`, `trainsets`, `duties`, `assignments`) are empty.

## Decision

The seed is loaded before step 2, with `railtrace seed --file data/seed.json`. It is the first step of `scripts/scenario.sh`.

## Alternatives considered

- **Not loading the seed**: without trainsets, stations and duties, the Worker cannot validate reports and everything would end up in quarantine. Steps 5 and 6 would not work either: the assignments of `VD-D03-20261103`, the `VD` line and the duty `VD-T01-20261104` only exist in the seed.

## Consequences

- The `seed` command is idempotent, so the script can run on a system where the seed has already been loaded.
