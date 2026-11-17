.PHONY: env clean db api

ENV_FILE := .env
ENV_VARS := DB_HOST DB_NAME DB_USER DB_PASSWORD DB_PORT DB_URL API_PORT
COMPOSE  := docker compose --env-file $(ENV_FILE)

env: $(ENV_FILE)

$(ENV_FILE):
	@for var in $(ENV_VARS); do echo "$$var=change-me" >> $@; done
	@echo "$@ criado com valores por defeito (change-me)"

db: $(ENV_FILE)
	$(COMPOSE) up -d db

api: $(ENV_FILE)
	$(COMPOSE) up -d --build api

clean:
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	find . -path ./.venv -prune -o -type f -name '*.py[co]' -exec rm -f {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
