.PHONY: all up down restart logs ps migrate env db api clean

ENV_FILE := .env
ENV_VARS := DB_HOST DB_NAME DB_USER DB_PASSWORD DB_PORT DB_URL API_PORT
COMPOSE  := docker compose --env-file $(ENV_FILE)

.DEFAULT_GOAL := all

all: up

up: $(ENV_FILE)
	$(COMPOSE) up -d --build --wait
	@$(COMPOSE) ps

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

# Serviços individuais
db: $(ENV_FILE)
	$(COMPOSE) up -d --wait db

api: $(ENV_FILE)
	$(COMPOSE) up -d --build api


env: $(ENV_FILE)

$(ENV_FILE):
	@for var in $(ENV_VARS); do echo "$$var=change-me" >> $@; done
	@echo "$@ criado com valores por defeito (change-me)"


clean:
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	find . -path ./.venv -prune -o -type f -name '*.py[co]' -exec rm -f {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
