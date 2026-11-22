# 0005 — Re-atribuição e rollups depois de alterar um assignment


## Contexto

- **R5**: uma medição pertence à duty do assignment da sua composição que cobre `measured_at`, com o início incluído e o fim excluído (`[started_at, ended_at)`). Sem assignment que a cubra, não é atribuída (`duty_id = NULL`).
- **R7**: por duty, os rollups por hora, o resumo da duty e as estatísticas por estação (`duty_hourly_rollups`, `duty_metric_summaries`, `duty_station_stats`).

Os assignments mudam depois de as medições já existirem: `POST /v1/duties/{code}/assignments` cria um, e `PATCH /v1/assignments/{id}` muda o início ou o fim (passo 5 do cenário). As medições já gravadas e os rollups das duties envolvidas têm de acompanhar a alteração.

## Decisão

**A re-atribuição é feita na mesma transação que a alteração do assignment** (`services/assignments.py`):
1. O assignment é criado ou alterado e enviado para a BD com `flush`. As exclusion constraints validam-no já aqui (ver [0006](6-r6-na-bd.md)).
2. `reattribute_measurements` (`services/attribution.py`) lê todos os assignments da composição e as medições dessa composição no intervalo afetado:
   - **criar**: o intervalo do novo assignment;
   - **alterar**: da menor à maior das datas antigas e novas (`min(início antigo, início novo)` até `max(fim antigo, fim novo)`), para apanhar as medições que entram e as que saem.
3. Para cada medição, `find_duty` (`domain/attribution.py`) decide a duty. Só as que mudam são escritas.
4. Os rollups são recalculados **para todas as duties de onde saíram medições e para onde entraram** (`refresh_rollups` em `services/rollups.py`).
5. Um só commit no fim: o assignment, as medições e os rollups mudam juntos ou não muda nada.

**Os rollups de uma duty são sempre recalculados de raiz** (`_recompute_duty`): apaga as linhas dessa duty nas três tabelas, lê todas as medições atribuídas à duty e volta a calcular com as funções puras de `domain/aggregation.py`. Não há atualizações incrementais (somar ou subtrair um valor). Antes disso, a linha da duty fica bloqueada (`SELECT … FOR UPDATE`) para dois recálculos da mesma duty não se cruzarem.

O mesmo `refresh_rollups` é usado pelo Worker: quando uma medição é criada, alterada ou apagada, são recalculadas a duty antiga e a nova (`_rebuild_measurement`). No `rebuild-read-models` (A4), os recálculos são adiados (`defer_rollups`) e cada duty é calculada uma só vez no fim.

## Alternativas consideradas

- **Re-atribuir todas as medições da composição**: daria o mesmo resultado, mas lê medições fora do intervalo que não podem mudar.

## Consequências

- Depois do `PATCH` responder, `/summary`, `/hourly`, `/stations` e `/readings` já refletem a nova atribuição. É o que o checkpoint final do cenário verifica.
- O custo de recalcular uma duty é proporcional ao número de medições dessa duty (uma duty tem 4 h, ~48 medições por composição).
- **Limitação conhecida**: o Worker e a alteração de um assignment não partilham nenhum lock. Imagina que o Worker está a criar uma medição da composição ao mesmo tempo que um assignment dessa composição é alterado. O Worker pode ter lido os assignments antigos, e a re-atribuição pode não ver a medição ainda por gravar. Nesse caso, a medição fica na duty antiga até ser processada outra vez (por exemplo com `railtrace rebuild-read-models`). No cenário isto não acontece, porque o passo 5 só corre depois de `pending = 0`.
