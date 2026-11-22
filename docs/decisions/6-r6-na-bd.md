# 0006 — R6 garantida pela base de dados


## Contexto

R6 (assignments): uma composição não pode estar em duas duties ao mesmo tempo, e uma duty não pode ter duas composições ao mesmo tempo. Os intervalos são `[started_at, ended_at)`, por isso um assignment que acaba às 08:40 e outro que começa às 08:40 não se sobrepõem.

Os assignments são escritos por três caminhos diferentes: o seed, `POST /v1/duties/{code}/assignments` e `PATCH /v1/assignments/{id}`. Pode haver pedidos em simultâneo.

## Decisão

A regra fica no schema, com duas **exclusion constraints** GiST em `assignments` (`models/assignment.py`, migração `da18af22626b`):

```sql
EXCLUDE USING gist (trainset_id WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)  -- ex_assignments_trainset_no_overlap
EXCLUDE USING gist (duty_id     WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)  -- ex_assignments_duty_no_overlap
```

- `tstzrange(…, '[)')` representa o intervalo com o início incluído e o fim excluído, igual ao da R5 (`AssignmentPeriod.covers`).
- `&&` = "os intervalos sobrepõem-se". Junto com `=` na composição (ou na duty), a BD recusa duas linhas com a mesma composição (ou duty) e intervalos sobrepostos.
- A extensão `btree_gist` (criada na migração) permite usar `=` sobre inteiros num índice GiST.
- `CHECK (ended_at > started_at)` (`ck_assignments_interval`) impede intervalos vazios ou invertidos.

O serviço não verifica sobreposições antes de escrever. Faz `flush` e traduz o erro da BD (`_flush_or_overlap` em `services/assignments.py`): `ExclusionViolation` passa a `AssignmentOverlapError`, que a API devolve como `409 Conflict` ("Assignment overlaps an existing one"). O frontend mostra essa mensagem tal como vem.

## Alternativas consideradas

- **Verificar no código com um `SELECT` antes do `INSERT`/`UPDATE`**: dois pedidos em simultâneo podiam passar os dois na verificação e gravar assignments sobrepostos. Para o evitar seria preciso bloquear tabelas ou usar `SERIALIZABLE`. A constraint é atómica e não depende de quem escreve.
- **Verificar no código e na BD**: duplicava a regra em dois sítios que podiam divergir (por exemplo na inclusão do fim), sem ganho. A BD é a única fonte da regra.
- **Trigger**: faz o mesmo que a exclusion constraint, com mais código e sem índice.

## Consequências

- Nenhum caminho de escrita (API, seed, SQL manual) consegue gravar assignments sobrepostos.
- O `PATCH` do passo 5 tem de ser feito por ordem: primeiro encurtar o fim da TS-0003, depois antecipar o início da TS-0005. Na ordem inversa, os dois sobrepunham-se por um momento e a BD recusava o pedido.
- **O que a BD não garante**: que a composição é da mesma linha da duty. Isso é verificado no serviço (`TrainsetWrongLineError` → `422`), porque obrigaria a comparar com outras tabelas, coisa que uma constraint não faz.
- O seed só ignora um assignment que já exista **exatamente igual** (`_insert_assignments` em `services/seed.py`). Se um assignment do seed tiver sido alterado (por exemplo pelo passo 5 do cenário), voltar a carregar o seed tenta inseri-lo outra vez, e a constraint recusa-o com `ExclusionViolation`. Por isso o cenário tem de correr numa BD limpa.
