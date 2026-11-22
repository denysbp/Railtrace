# 0004 — Independência da ordem de chegada em R3 e R4


## Contexto

Os relatórios de uma mesma medição podem chegar por qualquer ordem: em tempo real, num batch do depósito horas depois, ou a misturar os dois. O estado de uma medição e a deteção de conflitos não podem depender dessa ordem.

- **R3**: o estado de uma medição resulta das revisões aplicadas por ordem de `rev`. Um número define a métrica, `-` remove-a e uma chave ausente mantém-na. A estação vem da revisão com o `rev` mais alto. Sem métricas, a medição não aparece.
- **R4**: relatórios com a mesma identidade (`serial`, `measured_at`, `rev`) e conteúdo diferente estão em conflito, e todos eles vão para quarentena com o motivo `conflict`.

## Decisão

**Guardar sempre a revisão.** Todo o relatório válido dá uma linha em `report_revisions`, também quando é duplicado ou entra em conflito (`_apply_revision` em `services/process_report.py`). Assim, um relatório que chegue mais tarde encontra sempre todos os anteriores com a mesma identidade, qualquer que tenha sido o resultado deles.

**R4: a decisão olha para todas as revisões da identidade, não só para a última.** `classify_revision` (`domain/revisions.py`) recebe o conteúdo novo e o de todas as revisões já guardadas com a mesma identidade:
- nenhuma → `NEW` (aplicado);
- todas iguais (mesma estação, mesmas métricas, valores comparados como `Decimal`, por isso `11.6 == 11.60`) → `DUPLICATE`;
- alguma diferente → `CONFLICT`. O relatório novo **e todos os anteriores com essa identidade**, incluindo os já aplicados e os duplicados, passam a `quarantined/conflict`;
- se a identidade já estiver em conflito → `CONFLICT`, mesmo que o novo seja igual a uma das versões. Um conflito não se desfaz.

Assim, o conjunto final de estados é o mesmo para qualquer ordem. Por exemplo, com A = A′ ≠ B:
- A, A′, B → A aplicado, A′ duplicado, depois B dá conflito e A e A′ passam a conflito;
- B, A, A′ → B aplicado, A dá conflito (e B passa a conflito), A′ entra numa identidade em conflito.

Nos dois casos ficam os três em `conflict`.

**R3: a medição é recalculada de raiz a cada alteração.** `_rebuild_measurement` lê todas as revisões `applied` da medição (`serial`, `measured_at`), de todos os `rev`, e passa-as a `apply_revisions` (`domain/revisions.py`), que as **ordena por `rev`** antes de as aplicar. A medição é recalculada a partir das revisões, sem aplicar só a última por cima do estado anterior. Por isso, uma revisão `rev=1` que chega antes da `rev=0` dá o mesmo resultado. Quando a R4 tira revisões de `applied`, a medição é recalculada sem elas e pode voltar ao estado de outro `rev` ou desaparecer.

## Alternativas consideradas

- **Aplicar cada revisão por cima do estado atual da medição**: o resultado dependeria da ordem (`rev=0` a chegar depois de `rev=1` apagaria valores mais recentes) e não haveria forma de desfazer uma revisão que depois entra em conflito.
- **Não guardar duplicados nem conflitos**: um terceiro relatório diferente não saberia que já tinha havido duas versões, e o primeiro aplicado nunca passaria a conflito.
- **UNIQUE em `(trainset_id, measured_at, rev)`**: impediria guardar as várias versões de uma identidade, que é exatamente o que a R4 precisa de ver (ver [0001](1-responsabilidade-dos-modelos.md)).

## Consequências

- O estado efetivo (medição, quarentena por conflito) não depende da ordem de chegada. Isto está coberto por `tests/unit/test_revisions.py` e `tests/integration/test_process_report_r4.py`.
- **O que depende da ordem** é só *qual* de dois relatórios iguais fica `applied` e qual fica `duplicate` (R2: o primeiro a chegar). O conteúdo da medição é o mesmo nos dois casos. Por isso o Worker e o `rebuild-read-models` processam por `id` crescente, para darem o mesmo resultado.
- A garantia assume que os relatórios de uma identidade são processados um de cada vez. Com vários Workers em paralelo, dois relatórios da mesma identidade podiam ser classificados ao mesmo tempo sem se verem um ao outro. É mais uma razão para o compose arrancar um só Worker (ver [0003](3-api-para-worker.md)).
- Recalcular a medição a cada relatório custa uma leitura das suas revisões. São poucas por medição, por isso o custo é baixo.
