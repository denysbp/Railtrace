# 0001 — Ambiente local com Docker Compose e Makefile

**Estado:** Aceite · **Data:** 2026-11-16

## Contexto

Preciso de arrancar a base de dados e a API da mesma forma em qualquer máquina, sem instalar PostgreSQL localmente nem me lembrar de comandos longos.

## Decisão

- O `docker-compose.yml` tem dois serviços:
  - **`db`**: `postgres:17-alpine`, com os dados no volume `pgdata` e um healthcheck com `pg_isready`.
  - **`api`**: faz build a partir de `backend/Dockerfile` e só arranca quando o `db` está *healthy* (`depends_on: condition: service_healthy`).
- O `backend/Dockerfile` usa `python:3.14-slim` com o `uv` fixado na versão 0.13.0. As dependências são instaladas a partir do `uv.lock` (`uv sync --locked --no-dev`) numa camada separada do código, para aproveitar a cache do Docker.
- No container da API, o compose monta o `DB_URL` a partir de `DB_USER`, `DB_PASSWORD` e `DB_NAME`, com host `db`. Assim o URL dentro da rede Docker está sempre certo, seja qual for o valor do `.env` local.
- O `Makefile` expõe:
  - `make env`: cria o `.env` com todas as variáveis.
  - `make db`: `docker compose up -d db`.
  - `make api`: `docker compose up -d --build api`.
- O `backend/app/main.py` tem para já só um `GET /health`, para o container ter algo para servir.

## Alternativas consideradas

- **Correr a API fora do Docker e só o Postgres em container:** é mais rápido para desenvolver, mas o ambiente fica diferente do de avaliação. Continua possível: o `make db` arranca só a base de dados.
- **Usar `DB_URL` diretamente do `.env`:** é fácil apontar para `localhost`, que dentro do container não funciona.

## Consequências

- Os valores por defeito do compose (`${VAR:-default}`) só se aplicam se a variável não existir ou estiver vazia. Se o `.env` tiver `change-me`, tenho de o preencher antes de correr os serviços.
