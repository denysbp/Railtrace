# 0001 — Responsabilidade de cada modelo


## Contexto

Os modelos SQLAlchemy vivem em `backend/app/models/` e são todos registados em `app/models/__init__.py`, para ficarem em `Base.metadata` (Alembic e relationships). Este documento fixa o que cada modelo representa, quem o escreve e o que **não** é responsabilidade dele.

Os modelos só guardam dados e garantem a sua integridade (FKs, UNIQUE, CHECK, exclusion constraints). Não contêm regras de negócio: essas ficam em `domain/` (funções puras) e `services/` (coordenação e acesso à BD).

## Decisão

### Dados de referência

Carregados pelo comando `railtrace seed` (`services/seed.py`), de forma idempotente.

| Modelo | Tabela | Responsabilidade |
|---|---|---|
| `Line` | `lines` | Linha de metro, identificada pelo `code` único (ex.: `AZ`). |
| `Station` | `stations` | Estação física, identificada pelo `code` único (ex.: `SSE`). Uma estação de correspondência existe uma só vez. |
| `LineStation` | `line_stations` | Liga estações a linhas e guarda a `position` de cada estação no percurso. Permite que uma estação pertença a várias linhas. `UNIQUE(line_id, position)`. |
| `Trainset` | `trainsets` | Composição, identificada pelo `serial` único (ex.: `TS-0001`), com a sua linha (`home_line_id`). |
| `Duty` | `duties` | Serviço planeado numa linha, com início e fim planeados (`planned_end > planned_start`). |
| `Assignment` | `assignments` | Liga uma composição a uma duty durante um intervalo `[started_at, ended_at)`. Duas exclusion constraints (GiST, extensão `btree_gist`) impedem que uma composição esteja em duas duties ao mesmo tempo e que uma duty tenha duas composições ao mesmo tempo. Também é escrito pela API (`POST /duties/{code}/assignments`, `PATCH /assignments/{id}`). |

### Ingestão

Escritos pela API. A API só guarda o que recebe; não interpreta relatórios.

| Modelo | Tabela | Responsabilidade |
|---|---|---|
| `Batch` | `batches` | Ficheiro enviado pelo depósito (`POST /depot/batches`). Agrupa os relatórios desse ficheiro. |
| `ReportRaw` | `reports_raw` | Relatório tal como foi recebido, append-only: `raw_content` nunca é alterado. Guarda a origem (`batch_id` e `batch_line`, ou NULL quando veio em tempo real por `POST /reports`) e o resultado do processamento (`status` e, em quarentena, `quarantine_reason`). |

`ReportRaw` não tem campos interpretados (composição, instante, métricas): esses só existem depois do processamento, em `ReportRevision`.

### Telemetria

Escritos pelo Worker (ainda por implementar).

| Modelo | Tabela | Responsabilidade |
|---|---|---|
| `ReportRevision` | `report_revisions` | Relatório válido já interpretado: composição, `measured_at`, `rev` (≥ 0) e estação. Cada `ReportRaw` dá no máximo uma revisão (`report_raw_id` único). |
| `ReportRevisionMetric` | `report_revision_metrics` | Valores das métricas recebidos numa revisão, uma linha por métrica. PK `(report_revision_id, metric)`. |
| `Measurement` | `measurements` | Estado efetivo de uma medição depois de aplicadas as revisões válidas. Uma por composição e instante (`UNIQUE(trainset_id, measured_at)`). Guarda a atribuição a uma duty (`duty_id`, NULL quando não atribuída). |
| `MeasurementMetric` | `measurement_metrics` | Valores efetivos das métricas de uma medição. PK `(measurement_id, metric)`. |

### Read models dos endpoints de leitura (A2)

Escritos pelo Worker na mesma transação em que processa cada relatório. Os endpoints de leitura só leem estas tabelas (e `measurements`).

| Modelo | Tabela | Responsabilidade |
|---|---|---|
| `ReportOutcome` | `report_outcomes` | Resultado de cada relatório já processado: `status`, `quarantine_reason`, origem (`batch_id`, `batch_line`), linha original e hora de receção. Atualizado quando a R4 põe relatórios anteriores em conflito. Um relatório sem linha aqui ainda está por processar. Lido por `/depot/batches/{id}`, `/quarantine` e `/stats`. |
| `DutyHourlyRollup` | `duty_hourly_rollups` | R7: por duty, métrica e hora UTC, `count`, `value` e `coverage`. |
| `DutyMetricSummary` | `duty_metric_summaries` | R7: por duty e métrica, o valor sobre a duty inteira. |
| `DutyStationStats` | `duty_station_stats` | R7: por duty e estação, o número de relatórios e o maior valor `AX*`. |

### Enums (`models/enums.py`)

- `ReportStatus`: `pending`, `applied`, `duplicate`, `quarantined`.
- `QuarantineReason`: `malformed`, `bad_checksum`, `clock_invalid`, `unknown_trainset`, `unknown_station`, `unknown_metric`, `conflict`. `conflict` é só motivo de quarentena, não um status.

Na BD fica gravado o valor (`'pending'`), não o nome do membro (`values_callable`).

## Alternativas consideradas

- **Métricas como colunas** (`spd`, `kwh`, `ax1`…) em `report_revisions` e `measurements`: uma métrica nova obrigaria a alterar as tabelas. Com uma linha por métrica, uma métrica nova não muda o schema.
- **UNIQUE em `(trainset_id, measured_at, rev)`** em `report_revisions`: impediria guardar relatórios diferentes com a mesma identidade, que a R4 exige para detetar conflitos. Fica só um índice não único nessas colunas.
- **`station_id` obrigatório**: a maioria dos relatórios dos dados de exemplo não tem estação (`-`). Por isso `station_id` aceita NULL em `report_revisions` e `measurements`.

## Consequências

- Separação clara entre o que foi **recebido** (`ReportRaw`), o que foi **interpretado** (`ReportRevision`) e o **estado efetivo** (`Measurement`). Os read models podem ser reconstruídos a partir das revisões sem tocar nos relatórios originais.
- Um `ReportRaw` com revisão não pode ser apagado (FK `RESTRICT`), o que mantém o append-only.
- As métricas são apagadas com a revisão ou medição a que pertencem (`ON DELETE CASCADE`).
- Os valores usam `Numeric` sem precisão fixa (lidos como `Decimal`), para guardar o valor exatamente como foi recebido. `value` aceita NULL, para representar a remoção de uma métrica (R3).
- Nenhuma constraint garante que as métricas são conhecidas nem que `duty_id` é coerente com os assignments: são regras do Worker.
- `Measurement` não guarda que revisão lhe deu origem.
