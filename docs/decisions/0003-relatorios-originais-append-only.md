# 0003 — Relatórios originais append-only e estados de processamento

**Estado:** Aceite · **Data:** 2026-11-16

## Contexto

Os relatórios chegam como texto (`$TRN,...`) e podem vir mal formados, duplicados, com checksum errado ou com referências desconhecidas. Preciso de responder depressa à ingestão sem perder nada, e de poder reprocessar mais tarde.

## Decisão

- A API **só guarda o relatório original** em `reports_raw` e responde `202 Accepted` com o `report_id`. O parsing e o processamento são feitos pelo Worker.
- O `ReportRaw` **não tem** campos como `serial`, `measured_at`, `station` ou `metrics`, porque esses só se conhecem depois do parsing.
- O `raw_content` nunca é alterado nem apagado durante o processamento normal (append-only). O Worker só atualiza `status` e `quarantine_reason`.
- O `status` usa o enum `ReportStatus` (`pending`, `applied`, `duplicate`, `quarantined`, `conflict`) através de `SQLAlchemyEnum`, com `values_callable`. Assim a BD guarda o valor (`'pending'`) e não o nome do membro (`'PENDING'`), que é o que o SQLAlchemy faz por defeito.
- O `received_at` tem `server_default=now()`: a hora de receção é a do servidor de BD, não a do cliente.
- O motivo da quarentena fica numa coluna separada, `quarantine_reason`, com o enum `QuarantineReason`: `malformed`, `bad_checksum`, `clock_invalid`, `unknown_trainset`, `unknown_station`, `unknown_metric`. Os valores vêm dos motivos que aparecem no `data/expected.json`.
- Uma CHECK constraint garante a coerência nos dois sentidos:

  ```sql
  CHECK ((status = 'quarantined') = (quarantine_reason IS NOT NULL))
  ```

  Não pode haver quarentena sem motivo, nem motivo sem quarentena.

