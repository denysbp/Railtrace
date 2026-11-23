.PHONY: all up down restart logs ps migrate env db api clean

ENV_FILE := .env
ENV_VARS := DB_HOST DB_NAME DB_USER DB_PASSWORD DB_PORT DB_URL API_PORT
COMPOSE  := docker compose --env-file $(ENV_FILE)
DATA := data

.DEFAULT_GOAL := all


all: up migrate


up: $(ENV_FILE)
	$(COMPOSE) up -d --build  --wait
	@$(COMPOSE) ps

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

# populate db

scenario:
	@bash scripts/scenario.sh


live-stream: $(DATA)
	uv run $(DATA)/send_live.py --file $(DATA)/live-stream.txt

migrate:
	$(COMPOSE) exec api alembic upgrade head

# Individual services
db: $(ENV_FILE)
	$(COMPOSE) up -d --wait db

api: $(ENV_FILE)
	$(COMPOSE) up -d --build api

dev:
	uv run fastapi dev backend/app/main.py --host 0.0.0.0 --port 8000


worker:
	uv run -m backend.app.worker

env: $(ENV_FILE)

$(ENV_FILE):
	@for var in $(ENV_VARS); do echo "$$var=change-me" >> $@; done
	@echo "$@ created with default values (change-me)"


clean:
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	find . -path ./.venv -prune -o -type f -name '*.py[co]' -exec rm -f {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
