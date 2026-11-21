# 0002 — Carregar o seed antes do cenário


## Contexto

O cenário pede para correr os passos 2–7 (`scripts/scenario.sh` / `make scenario`) num sistema acabado de arrancar. O subject não diz se o seed (`data/seed.json`) tem de ser carregado antes disso ou não.

Num sistema acabado de arrancar, as tabelas de referência (`lines`, `stations`, `line_stations`, `trainsets`, `duties`, `assignments`) estão vazias.

## Decisão

O seed é carregado antes do passo 2, com `railtrace seed --file data/seed.json`. É o primeiro passo de `scripts/scenario.sh`.

## Alternativas consideradas

- **Não carregar o seed**: sem composições, estações e duties, o Worker não consegue validar os relatórios e tudo iria ficar em quarentena. Os passos 5 e 6 também não funcionariam: os assignments da `VD-D03-20261103`, a linha `VD` e a duty `VD-T01-20261104` só existem no seed.

## Consequências

- O comando `seed` é idempotente, por isso o script pode correr num sistema onde o seed já foi carregado.
