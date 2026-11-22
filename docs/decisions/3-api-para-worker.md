# 0003 — Como a API passa os relatórios ao Worker


## Contexto

Os relatórios chegam de duas formas: um a um em tempo real (`POST /v1/reports`) ou em ficheiro pelo depósito (`POST /v1/depot/batches`). Processar um relatório implica validar (R1), aplicar revisões (R2–R4), atribuir a uma duty (R5) e atualizar os rollups (R7). A API tem de responder depressa e não pode perder relatórios, mesmo que o Worker esteja parado ou falhe a meio.

## Decisão

A tabela `reports_raw` é a fila. Não há broker (Redis, RabbitMQ…): a API e o Worker só partilham o PostgreSQL.

**API (produtor)**
- `POST /v1/reports` grava uma linha em `reports_raw` com o texto tal como chegou, faz commit e responde `202 Accepted` com o `report_id`. Não interpreta o relatório.
- `POST /v1/depot/batches` cria um `Batch` e uma linha em `reports_raw` por cada linha do ficheiro (ignora linhas vazias e comentários `#`), tudo numa só transação (`services/ingest.py`). Responde `202` com o `batch_id`.
- `status` começa em `pending` e `received_at` é a hora de gravação na API. A R1 usa essa hora para o `clock_invalid`, e não a hora em que o Worker processa o relatório.

**Worker (consumidor)**, em `app/worker.py`:
- Pede o próximo relatório `pending` com `id` maior do que o último visto, por ordem de `id` (= ordem de chegada), com `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1`.
- Processa-o numa só transação (`services/process_report.py`, A3): muda o `status` em `reports_raw`, grava `report_outcomes` (A2), as revisões, a medição e os rollups, e faz commit uma vez no fim.
- Se houver um erro técnico, faz rollback e o relatório fica `pending`. O cursor avança mesmo assim, para um relatório com erro não bloquear os seguintes.
- Quando não há mais nada, o cursor volta a 0 (para repetir os `pending` que falharam) e o Worker espera 1 s antes de voltar a procurar.

**Coordenação com outras escritas**: o Worker e o `replay-quarantine` pegam num lock partilhado (`pg_advisory_xact_lock_shared`, `services/locks.py`). O `rebuild-read-models` (A4) pega no mesmo lock em modo exclusivo, por isso o processamento espera enquanto um rebuild corre. A ingestão na API não usa este lock e nunca fica bloqueada.

## Alternativas consideradas
- **Broker de mensagens**: mais um serviço para correr e manter. Haveria duas fontes de verdade (fila e BD), e seria preciso garantir que gravar na BD e publicar a mensagem acontecem juntos. Com a fila na BD, gravar o relatório *é* pô-lo na fila.


## Consequências

- Um relatório aceite (`202`) nunca se perde: fica em `reports_raw` até ser processado, mesmo que o Worker esteja em baixo.
- `pending` em `/v1/stats` e em `/v1/depot/batches/{id}` = recebidos − processados. O cenário espera por `pending = 0` antes de verificar os valores.
- A latência entre receber e processar um relatório é até ~1 s quando a fila está vazia.
- `SKIP LOCKED` permite vários Workers sem processarem o mesmo relatório. Mesmo assim, o compose arranca só um, porque a ordem de chegada importa para a R2 (ver [0004](4-ordem-r3-r4.md)).
- Um relatório que falha sempre por erro técnico volta a ser tentado em cada passagem. O erro aparece no log do Worker.
