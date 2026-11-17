# 0005 — Decisões em aberto no modelo de dados

**Estado:** Em aberto · **Data:** 2026-11-16

Pontos que identifiquei ao implementar os models e schemas, com a opção que segui por agora.

## 1. `conflict` é status ou motivo de quarentena?

O `data/expected.json` conta `conflict` dentro do bloco `quarantined`, mas eu decidi que `CONFLICT` é um **status** próprio.

- **Por agora:** mantenho `ReportStatus.CONFLICT` e não incluo `conflict` em `QuarantineReason`. O endpoint de estatísticas tem de somar `status = conflict` ao bloco `quarantined`.
- **Alternativa:** tratar o conflito como `status = quarantined` + `quarantine_reason = conflict` e tirar `CONFLICT` do status.

## 2. A linha da composição tem de coincidir com a linha da Duty

- **Por agora:** a regra é validada na camada `domain/`.
- **Alternativa (garantir na BD):** juntar `line_id` a `assignments` e criar duas FKs compostas, `(trainset_id, line_id) → trainsets(id, home_line_id)` e `(duty_id, line_id) → duties(id, line_id)`, com `UNIQUE` nesses pares. É mais robusto, mas duplica uma coluna e complica o modelo.

## 3. `ended_at` obrigatório

- **Por agora:** `NOT NULL`, porque todas as atribuições do `seed.json` têm fim.
- **Se surgirem atribuições "em curso":** basta tornar `ended_at` nullable. `tstzrange` trata `NULL` como infinito, e as exclusion constraints continuam a funcionar.

## 4. `TrainsetCreate` recebe `home_line_id` ou o código da linha?

- **Por agora:** `home_line_id`, que corresponde diretamente à FK.
- **Alternativa:** receber o código (`"AZ"`), como no `seed.json`. Nesse caso, a conversão código → id deve ser feita no service, não no schema.
