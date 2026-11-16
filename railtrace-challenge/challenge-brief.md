# Technical Challenge — Railtrace: Lisbon Metro telemetry

- **Deadline:** in the email that came with this brief.
- **Delivery:** a GitHub repository link.
- **Stack:** backend in Python or Node.js · frontend in **Next.js** · **PostgreSQL** with an ORM: **SQLAlchemy** (Python) or **Prisma** (Node.js) · Docker Compose.
- **No login.** There are no users, roles, passwords or API keys. Every page and every endpoint is open.
- **AI tools:** allowed. Describe your use in `AI_USAGE.md`.

**Materials.** Look at these first. They show the idea; this brief gives the rules.

| File | What it is |
|---|---|
| Video (link in the email) | A 63-second video: trains report to a control room, every report is checked, and a hot-axle incident is corrected afterwards. |
| [`inspiration/railtrace-slides.pdf`](inspiration/railtrace-slides.pdf) | 13 slides: the task, the network, the data, the rules, the architecture, the levels and a suggested order of work. |
| [`inspiration/dashboard-mockup.html`](inspiration/dashboard-mockup.html) | An example dashboard. Open it in a browser. Its numbers come from `data/expected.json`. |

> **The example dashboard is for inspiration only.** It is plain HTML so that you can open it without installing anything. It is not a template and not a requirement. **Your interface must be a Next.js app** (section 7). The design is your choice.

## 1. The task

The trains of the Lisbon metro send telemetry. Build a system that:

1. receives telemetry reports (live, and late from depot downloads);
2. assigns each report to the duty that the trainset was doing **at the time of the measurement**;
3. stays correct when data is late, repeated, corrected, or when the control room corrects an assignment afterwards;
4. shows the network, the duties and the data in a Next.js web app.

The network is the real one: four lines, real stations in real order, as it runs in November 2026. The trains, duties and data are fictional.

The work is in levels (section 9). Finish Level 1 first. Correct behavior is more important than more features.

## 2. Terms

| Term        | Meaning                                                                                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Line        | `AZ` Linha Azul (Reboleira – Santa Apolónia), `AM` Linha Amarela (Odivelas – Rato), `VD` Linha Verde (Telheiras – Cais do Sodré), `VM` Linha Vermelha (São Sebastião – Aeroporto). |
| Station     | A metro station with a 3-letter code, for example `MPO` Marquês de Pombal. Some stations are on two lines.                                                                         |
| Trainset    | One train, serial `TS-0000`, with a home line. Its onboard unit sends a report every 5 minutes, also in the depot.                                                                 |
| Duty        | A trainset's work block on one line, shuttling between the two ends. Code `VD-D03-20261103` = Linha Verde, duty 3, 3 November 2026.                                                |
| Assignment  | "Trainset X worked duty Y from time A to time B". A duty can have more than one assignment (a broken train is replaced).                                                           |
| Report      | One line of text from a trainset (section 3).                                                                                                                                      |
| Measurement | All values of one trainset at one instant. Several reports can describe it (copies, corrections).                                                                                  |

## 3. Input

### 3.1 Report format

```
$TRN,<serial>,<measured_at>,<rev>,<station>,<metrics>*<checksum>
```

| Field         | Rule                                                                                                                    |
| ------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `serial`      | `TS-` + 4 digits                                                                                                        |
| `measured_at` | ISO 8601 with seconds, and `Z` or `±hh:mm`. Compare as a UTC instant.                                                   |
| `rev`         | Integer ≥ 0. The first report of a measurement is 0. Corrections use higher values.                                     |
| `station`     | The station where the train was at `measured_at`: a 3-letter code, or `-` (not at a station, for example in the depot). |
| `metrics`     | One or more `KEY=VALUE`, separated by `;`. Value: a decimal number, or `-`.                                             |
| `checksum`    | Two hex digits, any case: XOR of all bytes between `$` and `*`.                                                         |

Metric keys: `SPD` (average speed, km/h), `KWH` (energy used in the 5 minutes, kWh), `AX1` … `AX8` (axle bearing temperature, °C).

```
$TRN,TS-0001,2026-11-03T07:10:00Z,0,RES,SPD=27.4;KWH=11.62;AX4=34.9*10
$TRN,TS-0001,2026-11-03T07:10:00Z,1,RES,AX4=31.9;AX8=-*38
```

### 3.2 Files in `data/`

| File | Content |
|---|---|
| `seed.json` | Lines (with stations in order), stations, trainsets, duties, assignments. |
| `depot-batch-01.txt` | Depot download for 2 November 2026. Starts with a UTF-8 BOM. |
| `live-stream.txt` | Live reports for 3–4 November 2026. One report per line. |
| `depot-batch-02.txt` | Depot download for 3–4 November 2026. CRLF line endings. Copies, corrections and errors. |
| `send_live.py` | Sends `live-stream.txt` to your API, one POST per line. |
| `expected.json` | The expected API results for the scenario (section 8). |

In depot files, ignore empty lines and lines that start with `#`. Every other line is a report. One bad line must not stop the others.

We test with other files that follow the same rules. Do not hard-code values from these files.

## 4. Rules

**R1 — Quarantine.** Check each report in this order. The first failure is the reason. A quarantined report is kept and does not change anything.

| # | Check | Reason |
|---|---|---|
| 1 | Form `$...*hh`, no other `$` or `*` | `malformed` |
| 2 | Checksum correct | `bad_checksum` |
| 3 | 6 fields, type `TRN`, each field valid, no repeated key, ≥ 1 metric | `malformed` |
| 4 | All metric keys are known | `unknown_metric` |
| 5 | Station is `-` or a known station | `unknown_station` |
| 6 | Trainset is registered | `unknown_trainset` |
| 7 | `measured_at` ≥ 2020-01-01 and ≤ receive time + 10 min | `clock_invalid` |
| 8 | Not disputed (R4) | `conflict` |

**R2 — Duplicates.** A measurement is `(serial, measured_at)`. A report is `(serial, measured_at, rev)`. Two reports with the same identity are identical if the station is the same and the metrics are equal as numbers (`11.6` = `11.60`). An identical report is a `duplicate` and does not change anything.

**R3 — Revisions.** The state of a measurement = its revisions applied in ascending `rev` order: a number sets the metric, `-` removes it, a missing key keeps its value. The station comes from the highest revision. Revisions arrive in any order. **The result must not depend on arrival order.** A measurement with no metrics left does not appear.

**R4 — Conflicts.** Same identity, different content = disputed revision. **All** reports with that identity become `conflict`, including one already applied. The measurement falls back to its other revisions. Also independent of arrival order.

**R5 — Attribution.** An assignment covers `[started_at, ended_at)`. A measurement belongs to the duty whose assignment of that trainset covers `measured_at`. If none covers it, it is unattributed (for example, in the depot). When an assignment is created or changed, all affected measurements and rollups change too.

**R6 — Assignment invariants.** `ended_at` > `started_at`. A trainset is in at most one duty at any instant. A duty has at most one trainset at any instant. The trainset's home line is the duty's line. **The database enforces the two "at most one" rules**, so that concurrent requests cannot break them. If your ORM cannot express such a constraint, add it in a migration with plain SQL.

**R7 — Rollups.** Per duty, metric and UTC hour: `count`, `value`, `coverage` = min(count / 12, 1), 3 decimals. `value` depends on the metric: `SPD` mean, `KWH` sum, `AX*` max. The duty summary uses the same rule over the whole duty. Round to 2 decimals. Per duty and station: number of reports and the highest `AX*` value. Rollups change when data or assignments change.

**R8 — Replay.** A quarantined report can be checked again (R1) with the current state, for example after a new trainset is registered.

## 5. Mandatory architecture

**A1 — Keep the rules apart from the framework.** Put the rules of section 4 (parsing, checks, revisions, attribution, rollups) in their own folder, `domain/`, as plain functions or classes. Code in `domain/` does not import the web framework, the ORM or the database. The API and the worker call it. Its unit tests run without a database.

**A2 — Write path ≠ read path.** Ingest endpoints store the raw report and return `202`. They parse nothing. A background process, the worker, applies all rules and writes the read models. Query endpoints read only the read models.

*Read models* are the tables that the pages and the query endpoints read. They contain results that the worker has already calculated, for example: the current state of each measurement, the duty it belongs to, the hourly rollups and the values per station. The raw reports are not a read model.

How the API passes new reports to the worker is your choice. Explain it in a decision record.

**A3 — One transaction per item.** If the worker stops at any point, nothing is half-written. The item is processed again after a restart.

**A4 — Rebuildable read models.** Raw reports are append-only. A CLI command rebuilds all read models from them; every API answer is the same afterwards.

**A5 — One place for aggregation.** The R7 rule per metric (mean, sum, max) is defined in one place (Strategy pattern). A new metric kind needs one new strategy, not changes in many files.

## 6. API

Paths start with `/v1`. JSON bodies. Times in UTC with `Z`. No authentication. Use these paths and field names. You can add fields. Errors: `{"error": {"code", "message"}}`.

| Endpoint | Result |
|---|---|
| `POST /reports` | `text/plain`, one report, max 1 KB → `202 {"report_id"}` |
| `POST /depot/batches` | Multipart field `file`, max 5 MB (else 413), UTF-8 (else 400, nothing stored) → `202 {"batch_id"}` |
| `GET /depot/batches/{id}` | `{"batch_id","lines","applied","duplicate","pending","quarantined":{reason: n}}` — current outcome of each report |
| `GET /lines` | All lines, each with its stations in order (`code`, `name`) |
| `GET /duties?date=YYYY-MM-DD&line=` | Duties of that day (optionally one line) |
| `GET /duties/{code}` | Duty and its assignments (with `id`) |
| `GET /duties/{code}/readings?metric=` | `{"duty","metric","points":[{"measured_at","value","trainset","station"}]}` |
| `GET /duties/{code}/hourly?metric=` | `{"duty","metric","buckets":[{"hour","count","value","coverage"}]}` |
| `GET /duties/{code}/summary` | `{"duty","trainsets","measurements","metrics":{"SPD":…,"KWH":…,"AX1":…}}` |
| `GET /duties/{code}/stations` | `{"duty","line","stations":[{"station","name","reports","max_axle"}]}` — every station of the line, in line order |
| `POST /duties/{code}/assignments` | `{"trainset","started_at","ended_at"?}` → 201. Overlap 409. Trainset of another line 422. |
| `PATCH /assignments/{id}` | `{"started_at"?,"ended_at"?}`. Same errors. |
| `POST /trainsets` | `{"serial","line"}` → 201. Exists: 409. |
| `GET /quarantine?reason=&limit=` | Reports with reason, raw line, source, received time |
| `GET /stats` | `{"reports_total","measurements","attributed","unattributed","quarantined":{…},"pending"}` — `pending` = reports not processed yet |

## 7. User interface (Next.js)

| Page | Content |
|---|---|
| `/` | The four lines, each in its colour (blue, yellow, green, red) with its stations in order. Click a line to see its duties. |
| `/duties` | Date and line filters. Table: code, line, planned times, trainsets, measurements, max axle temperature. Highlight a duty where any axle reached 80 °C or more. |
| `/duties/[code]` | Summary values. A strip of the line's stations in order; mark each station where an axle reached 80 °C or more. A speed chart and an axle-temperature chart over time, one colour per trainset. Hourly table with a metric selector. Assignments table: add an assignment and change start and end times; show API errors (for example a 409) in clear text. |
| `/trainsets/new` | Register a trainset. |

There is no login page. Visual design is free; clarity counts, decoration does not.

Build these pages in **Next.js**. The example dashboard in `inspiration/dashboard-mockup.html` shows one possible look. Use it for ideas only. Do not submit it, and do not wrap it in a Next.js page.

## 8. Run it

`docker compose up --build` starts everything on a clean machine: `db`, `api`, `worker`, `web`. Named volume for the database. Configuration from environment variables, with a committed `.env.example`. Health checks; services wait for the database. Migrations and seed run automatically; the seed is safe to run twice.

CLI, run through Compose (for example `docker compose run --rm cli <command>`):

| Command | Does |
|---|---|
| `seed --file data/seed.json` | Loads the seed (idempotent) |
| `replay-quarantine --reason <r> [--dry-run]` | R8. `--dry-run` only prints. |
| `rebuild-read-models` | A4 |

**Scenario.** `expected.json` has the API results at checkpoint A and at the end.

1. Start the system.
2. Upload `depot-batch-01.txt`.
3. Send `live-stream.txt`.
4. Upload `depot-batch-02.txt`. Wait for `pending` = 0. **Checkpoint A.**
5. On duty `VD-D03-20261103`, TS-0003 was withdrawn at **08:40Z** with a hot axle, not at 10:00Z. Set the TS-0003 assignment end to `2026-11-03T08:40:00Z`, then the TS-0005 assignment start to the same time. (The other order gives 409. That is correct.)
6. Register `TS-0099` on line `VD`, assign it to `VD-T01-20261104` from `09:00Z` to `15:00Z` that day, and run `replay-quarantine --reason unknown_trainset`.
7. Wait for `pending` = 0. **Final checkpoint.**

Add a script (`make scenario` or `scripts/scenario.sh`) that runs steps 2–7 on a fresh system and prints PASS or FAIL for each value in `expected.json`.

## 9. Levels

**Level 1 — Core**
- Compose. Schema with the ORM (SQLAlchemy or Prisma), with migrations, foreign keys and the R6 constraints. Seed (lines and stations included).
- Both ingest paths and the worker (A2, A3).
- R1, R2, R3, R5. Readings endpoint. Assignment creation.
- Rules in `domain/` (A1), with unit tests that run without a database.
- UI: lines page, duties list, duty page with the speed chart.

**Level 2 — Expected**
- R4. Assignment changes with re-attribution. R7 hourly, summary and stations (A5).
- `replay-quarantine`, `rebuild-read-models`, batch status, stats.
- UI: station strip, axle chart, hourly table, assignment editing, trainset registration.
- Scenario script passes.

**Level 3 — Stretch (choose)**
- A test that stops the worker during a large upload and checks the final state.
- A property-based test: shuffled input, same final state.
- 20,000 depot lines processed in under 3 minutes on a laptop.
- Live updates on the duty page (Server-Sent Events).
- An automated check that `domain/` imports no framework, ORM or database code.

## 10. Deliver

- Source, Dockerfiles, migrations, tests.
- `README.md`: how to run, test, run the scenario, use the CLI; levels finished.
- `docs/schema.md`: ER diagram (Mermaid is fine) and the reason for each constraint and index. **Commit a first version early, before most of the code.**
- `docs/decisions/`: at least 5 short records (decision, rejected options, consequences): how the API passes new reports to the worker; order independence for R3/R4; re-attribution and rollups after an assignment change; database enforcement of R6; how `domain/` stays apart from the framework and the ORM.
- `AI_USAGE.md`: tools, for which parts, and one case where the AI was wrong and how you found it.

## 11. Evaluation

We run your system with hidden data in a different order, plus failure tests (concurrent requests, a stopped worker). We read the schema, code, tests and decision records. Then a 45-minute call: you explain the design and change one rule live in your code.
