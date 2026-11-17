# 0002 — Separar models SQLAlchemy de schemas Pydantic

**Estado:** Aceite · **Data:** 2026-11-16

## Contexto

O backend usa FastAPI, SQLAlchemy 2.0 e Pydantic v2. Preciso de representar as tabelas da base de dados e também o contrato da API, e as duas coisas mudam por razões diferentes.

## Decisão

- **`app/models/`** tem os modelos SQLAlchemy, que descrevem *como os dados ficam guardados*: tabelas, tipos, FKs e constraints. Uso o estilo 2.0 (`Mapped`, `mapped_column`, `relationship`).
- **`app/schemas/`** tem os modelos Pydantic, que descrevem *o contrato HTTP*: o que o cliente envia (`*Create`, `*Update`) e o que recebe (`*Response`). Os schemas de resposta usam `ConfigDict(from_attributes=True)`, para eu poder fazer `XResponse.model_validate(objeto_orm)`.
- Os valores controlados são `Enum`s em `app/models/enums.py` (`ReportStatus`, `QuarantineReason`), para não haver strings soltas pelo código.
- O `app/models/__init__.py` importa todos os modelos. Assim ficam registados em `Base.metadata`, o que é necessário para o Alembic e para resolver as relationships.
- Os imports entre models usam `TYPE_CHECKING` e anotações em string, para evitar imports circulares (por exemplo `Line` ↔ `Trainset`).

### Entidades

| Model | Tabela | Campos principais |
|-------|--------|-------------------|
| `Line` | `lines` | `code` (único, `String(2)`), `name` |
| `Trainset` | `trainsets` | `serial` (único), `home_line_id → lines.id` |
| `Duty` | `duties` | `code` (único), `line_id → lines.id`, `planned_start`, `planned_end` |
| `Assignment` | `assignments` | `trainset_id → trainsets.id`, `duty_id → duties.id`, `started_at`, `ended_at` |
| `ReportRaw` | `reports_raw` | `raw_content`, `received_at`, `status`, `quarantine_reason` |

### Tipos

- **Datas:** `DateTime(timezone=True)` nos models e `AwareDatetime` nos schemas. Os relatórios vêm em UTC (`Z`), e uma data sem timezone é ambígua, por isso é rejeitada logo à entrada com 422.
- **Texto:** `String(n)` para códigos com tamanho conhecido e `Text` para `raw_content`, que tem de ficar guardado sem truncar nada.
- **Chaves primárias:** `int`. É simples e chega para o volume do projeto.

### Foreign keys e relationships

- Todas as FKs usam `ondelete="RESTRICT"`: apagar uma linha que tem composições é quase de certeza um erro, por isso a BD recusa em vez de apagar em cascata.
- As relationships são bidirecionais com `back_populates`: `Line ↔ Trainset`, `Line ↔ Duty`, `Trainset ↔ Assignment` e `Duty ↔ Assignment`.
- A `Assignment` é uma entidade própria e não uma tabela N:N simples, porque tem dados seus (o intervalo).

### Schemas

| Ficheiro | Schemas |
|----------|---------|
| `line.py` | `LineCreate`, `LineResponse` |
| `trainset.py` | `TrainsetCreate`, `TrainsetResponse` |
| `report.py` | `ReportAcceptedResponse` (`report_id`), `ReportResponse` |
| `duty.py` | `DutyResponse` |
| `assignment.py` | `AssignmentCreate`, `AssignmentUpdate`, `AssignmentResponse` |

- Não existe schema de request para `POST /reports`, porque o endpoint recebe `text/plain`. O `ReportAcceptedResponse` é o corpo do 202 Accepted.
- O `AssignmentUpdate` só permite alterar o intervalo. Trocar a composição ou a Duty é uma nova Assignment.
- Os schemas validam tipos, campos obrigatórios e a coerência interna do próprio payload (`ended_at > started_at`). As regras que precisam da BD (sobreposições, linha da composição = linha da Duty) ficam na camada `domain/`.

## Alternativas consideradas

- **SQLModel (uma só classe para ORM e API):** tem menos código, mas mistura responsabilidades. Por exemplo, a tabela tem `raw_content` e a resposta 202 só deve expor `report_id`.

## Consequências

- Há alguma duplicação de campos entre model e schema. Aceito-a em troca de poder mudar a BD sem partir o contrato da API, e vice-versa.
