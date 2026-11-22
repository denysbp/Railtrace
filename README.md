# Railtrace

Ingestão e análise de telemetria de composições de metro. É composto por quatro partes:

- **API** (FastAPI): recebe os relatórios e serve as leituras;
- **Worker**: aplica as regras a cada relatório;
- **PostgreSQL**: guarda os dados e serve de fila entre a API e o Worker;
- **frontend** (Next.js): as páginas de consulta.

```
backend/app/
  api/        rotas HTTP (só traduzem pedidos e erros)
  services/   coordenação: BD, transações, locks
  domain/     regras como funções puras (só biblioteca padrão)
  models/     tabelas SQLAlchemy e constraints
  schemas/    bodies e respostas (Pydantic)
  worker.py   consumidor da fila reports_raw
  cli.py      comando `railtrace`
backend/migrations/   Alembic
backend/tests/        unit/ (sem BD) e integration/ (railtrace-test)
frontend/             Next.js (serviço `web`)
scripts/scenario.sh   cenário automático (passos 2–7 + checkpoints)
data/                 seed, batches, live stream e valores esperados
docs/                 schema.md e decisions/
```

## Requisitos

- Docker com Docker Compose
- `make`
- [uv](https://docs.astral.sh/uv/) e Python 3.14: só para correr os testes, o CLI ou a API fora do Docker
- Node 22: só para desenvolver o frontend fora do Docker

## Como correr

```bash
make env       # cria .env com valores "change-me" (se ainda não existir) — edita-o
make           # = make up + make migrate
```

O `.env` precisa, no mínimo, de `DB_NAME`, `DB_USER`, `DB_PASSWORD` e `API_PORT`. Dentro do compose, `DB_HOST` e `DB_URL` são definidos pelo próprio compose.

| Serviço | O que é | Endereço |
|---|---|---|
| `db` | PostgreSQL 17 | `localhost:${DB_PORT:-5432}` |
| `api` | FastAPI | http://localhost:8000, documentação em http://localhost:8000/docs |
| `worker` | Processa a fila de relatórios | só tem logs (`make logs`) |
| `web` | Frontend Next.js | http://localhost:3000 (`WEB_PORT` para mudar) |
| `cli` | Comando `railtrace` (perfil `cli`, não arranca com `up`) | `docker compose run --rm cli …` |

Outros alvos do `Makefile`:

| Comando | O que faz |
|---|---|
| `make up` / `make down` / `make restart` | Arranca, para ou reinicia todos os serviços |
| `make migrate` | `alembic upgrade head` dentro do contentor `api` |
| `make logs` / `make ps` | Logs e estado dos serviços |
| `make live-stream` | Envia `data/live-stream.txt` para `POST /v1/reports`, uma linha por pedido |
| `make dev` | API em modo desenvolvimento, fora do Docker (porta 8000) |
| `make worker` | Worker fora do Docker |
| `make clean` | Apaga caches Python e de testes |

Frontend fora do Docker:

```bash
cd frontend && npm install && npm run dev    # http://localhost:3000, usa API_URL (por omissão http://localhost:8000)
```

### Endpoints

| Método | Caminho | |
|---|---|---|
| POST | `/v1/reports` | Um relatório em `text/plain` (máx. 1 KB) → `202` |
| POST | `/v1/depot/batches` | Ficheiro do depósito (`multipart`, máx. 5 MB) → `202` |
| GET | `/v1/depot/batches/{id}` | Resultado de cada linha do batch |
| GET | `/v1/lines` | Linhas com as estações por ordem |
| GET | `/v1/duties?date=YYYY-MM-DD&line=` | Duties de um dia |
| GET | `/v1/duties/{code}` | Duty e os seus assignments |
| GET | `/v1/duties/{code}/readings?metric=` | Valores de uma métrica ao longo do tempo |
| GET | `/v1/duties/{code}/hourly?metric=` | Rollups por hora UTC |
| GET | `/v1/duties/{code}/summary` | Composições, medições e resumo por métrica |
| GET | `/v1/duties/{code}/stations` | Estações da linha com o máximo de eixo |
| POST | `/v1/duties/{code}/assignments` | Novo assignment (`409` se sobrepuser outro) |
| PATCH | `/v1/assignments/{id}` | Muda início/fim (`409` se sobrepuser outro) |
| POST | `/v1/trainsets` | Regista uma composição |
| GET | `/v1/quarantine?reason=&limit=` | Relatórios em quarentena |
| GET | `/v1/stats` | Totais |

## Testes

```bash
uv run pytest backend/tests/unit        # só o domínio: sem BD, ~0,2 s
uv run pytest backend/tests             # unitários + integração
```

Os testes de integração correm **só** na base de dados `railtrace-test`. O `backend/tests/conftest.py` força `DB_NAME=railtrace-test` e a suite recusa-se a correr noutra BD. Antes de cada teste, as tabelas são esvaziadas e o seed é carregado outra vez. Se a BD não estiver acessível, os testes de integração são ignorados (`skip`).

Para criar a BD de testes (uma vez), com o `db` a correr:

```bash
docker compose --env-file .env exec db sh -c 'createdb -U "$POSTGRES_USER" railtrace-test'
DB_NAME=railtrace-test DB_HOST=localhost uv run alembic upgrade head
```

## Cenário

```bash
make scenario        # = bash scripts/scenario.sh
```

O script corre contra a API em `http://127.0.0.1:8000` (pode mudar com `API=…`) e faz, por ordem:

1. carrega o seed (`railtrace seed`, ver [decisão 0002](docs/decisions/2-carregar-o-seed.md));
2. envia `depot-batch-01.txt`;
3. envia `live-stream.txt`, uma linha por pedido;
4. envia `depot-batch-02.txt`, espera por `pending = 0` e verifica o **checkpoint A** contra `data/expected.json`;
5. retira a TS-0003 da `VD-D03-20261103` às 08:40Z: primeiro o `PATCH` do fim da TS-0003, depois o do início da TS-0005;
6. regista a TS-0099 na linha VD, cria o assignment em `VD-T01-20261104` e corre `replay-quarantine --reason unknown_trainset`;
7. espera por `pending = 0` e verifica o **checkpoint final**.

Cada valor aparece como `PASS`/`FAIL`, e no fim o script mostra `SCENARIO: PASS` ou `SCENARIO: FAIL (n valores errados)` (código de saída 1).

**Tem de correr numa BD limpa.** O passo 5 altera assignments do seed. Ao voltar a correr, o passo 1 tenta inserir outra vez o assignment original, e isso viola `ex_assignments_duty_no_overlap` (ver [decisão 0006](docs/decisions/6-r6-na-bd.md)). Para recomeçar do zero, apaga o volume com `docker compose --env-file .env down -v && make`, ou aponta o `.env` para outra BD vazia e corre `make migrate`. **Atenção:** `down -v` apaga todos os dados.

## CLI

Dentro do Docker (o serviço `cli` monta `./data` em `/app/data` só para leitura):

```bash
docker compose --env-file .env run --rm cli seed --file data/seed.json
docker compose --env-file .env run --rm cli replay-quarantine --reason unknown_trainset [--dry-run]
docker compose --env-file .env run --rm cli rebuild-read-models
```

Fora do Docker, o mesmo comando (usa o `.env`, com `DB_HOST=localhost`): `uv run railtrace <comando> …`.

| Comando | O que faz |
|---|---|
| `seed --file <json>` | Carrega linhas, estações, composições, duties e assignments. Idempotente para o que não foi alterado. |
| `replay-quarantine --reason <motivo> [--dry-run]` | **R8**: volta a aplicar as regras aos relatórios em quarentena com esse motivo (ex.: depois de registar uma composição). Com `--dry-run` só mostra o que mudaria. Motivos: `malformed`, `bad_checksum`, `clock_invalid`, `unknown_trainset`, `unknown_station`, `unknown_metric`, `conflict`. |
| `rebuild-read-models` | **A4**: apaga revisões, medições, resultados e rollups e volta a processar todos os relatórios por ordem de chegada, numa só transação. O Worker espera até acabar. |

## Níveis concluídos

[x] - "level 1"
[x] - "level 2"
[] - "level 3"

## Documentação

- [`docs/schema.md`](docs/schema.md): todas as tabelas, colunas e constraints.
- [`docs/decisions/`](docs/decisions/): decisões de arquitetura:
  - [1](docs/decisions/1-responsabilidade-dos-modelos.md) responsabilidade de cada modelo
  - [2](docs/decisions/2-carregar-o-seed.md) carregar o seed antes do cenário
  - [3](docs/decisions/3-api-para-worker.md) como a API passa os relatórios ao Worker
  - [4](docs/decisions/4-ordem-r3-r4.md) independência da ordem em R3/R4
  - [5](docs/decisions/5-reatribuicao-e-rollups.md) re-atribuição e rollups depois de alterar um assignment
  - [6](docs/decisions/6-r6-na-bd.md) R6 garantida pela BD
