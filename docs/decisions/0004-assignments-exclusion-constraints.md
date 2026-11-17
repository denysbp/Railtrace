# 0004 — Não sobreposição de Assignments com exclusion constraints

**Estado:** Aceite · **Data:** 2026-11-16

## Contexto

Uma Assignment liga uma composição a uma Duty no intervalo `[started_at, ended_at)`. As regras são:

1. Uma composição não pode estar em duas Duties ao mesmo tempo.
2. Uma Duty não pode ter duas composições ao mesmo tempo.
3. `ended_at` tem de ser posterior a `started_at`.

Uma verificação feita só em Python ("existe alguma sobreposta?" seguido de "insere") tem uma race condition: dois pedidos simultâneos passam os dois na verificação.

## Decisão

Proteger as regras na própria base de dados PostgreSQL:

```sql
CHECK (ended_at > started_at)

EXCLUDE USING gist (trainset_id WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)
EXCLUDE USING gist (duty_id     WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)
```

- Lê-se assim: não podem existir duas linhas com o mesmo `trainset_id` (ou `duty_id`) cujos intervalos se intersetem (`&&`).
- `'[)'` dá o intervalo semiaberto: uma atribuição que acaba às 11h não colide com outra que começa às 11h.
- No model, isto está declarado com `ExcludeConstraint` em `__table_args__` (`app/models/assignment.py`).
- A mesma regra `ended_at > started_at` também está nas `Duty` (`planned_end > planned_start`) e no schema Pydantic, para dar um 422 claro antes de chegar à BD.

### Validação

Testei contra um PostgreSQL 17 real:
- **Aceite:** as atribuições adjacentes `[7h, 11h)` + `[11h, 15h)`.
- **Rejeitado:** a mesma composição sobreposta (`ex_assignments_trainset_no_overlap`).
- **Rejeitado:** a mesma Duty sobreposta (`ex_assignments_duty_no_overlap`).
- **Rejeitado:** `ended_at <= started_at` (`ck_assignments_interval`).

## Alternativas consideradas

- **Só validação na camada `domain/`:** não é atómica sob concorrência.
- **`SELECT ... FOR UPDATE` / lock da tabela:** funciona, mas é mais complexo e fácil de esquecer num caminho de código novo.

## Consequências

- **A migration inicial tem de criar a extensão `btree_gist`** antes da tabela `assignments`, porque sem ela o GiST não aceita `=` sobre `integer`:

  ```sql
  CREATE EXTENSION IF NOT EXISTS btree_gist;
  ```

- A camada `domain/` continua a validar antes de inserir, para dar mensagens de erro úteis. A BD é a última linha de defesa.
- Os índices GiST das constraints começam por `trainset_id` / `duty_id`, por isso não criei índices extra nessas FKs.
