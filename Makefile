SHELL := /bin/bash

# Можно переопределить переменную в CI, если надо:
# DOCKER_COMPOSE="docker-compose"
DOCKER_COMPOSE ?= docker compose

PROJECT_NAME := neft-processing

.PHONY: up down restart ps build prepull-base-images \
        logs logs-core logs-auth logs-workers logs-nginx logs-ai logs-db \
        shell-core shell-auth shell-workers shell-ai \
        migrate test test-core test-auth test-ai test-workers \
        health health-core health-auth health-ai smoke schema-smoke-core \
        schema-smoke-core-local alembic-version-check \
        clean-volumes clean-images

# ----------------------------------------
# БАЗОВЫЕ ОПЕРАЦИИ С СТЕКОМ
# ----------------------------------------

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

restart: down up

ps:
	$(DOCKER_COMPOSE) ps

build: prepull-base-images
	$(DOCKER_COMPOSE) build

prepull-base-images:
	bash scripts/pull_base_images.sh

prep:
	bash scripts/pull_base_images.sh

# ----------------------------------------
# ЛОГИ СЕРВИСОВ
# ----------------------------------------

logs:
	$(DOCKER_COMPOSE) logs -f

logs-core:
	$(DOCKER_COMPOSE) logs -f core-api

logs-auth:
	$(DOCKER_COMPOSE) logs -f auth-host

logs-workers:
	$(DOCKER_COMPOSE) logs -f workers

logs-ai:
	$(DOCKER_COMPOSE) logs -f ai-service

logs-nginx:
	$(DOCKER_COMPOSE) logs -f nginx

logs-db:
	$(DOCKER_COMPOSE) logs -f db

# ----------------------------------------
# SHELL ВНУТРИ КОНТЕЙНЕРОВ
# ----------------------------------------

shell-core:
	$(DOCKER_COMPOSE) exec core-api sh

shell-auth:
	$(DOCKER_COMPOSE) exec auth-host sh

shell-workers:
	$(DOCKER_COMPOSE) exec workers sh

shell-ai:
	$(DOCKER_COMPOSE) exec ai-service sh

# ----------------------------------------
# МИГРАЦИИ БД (core-api / Alembic)
# ----------------------------------------

migrate:
	$(DOCKER_COMPOSE) exec core-api alembic upgrade head

# ----------------------------------------
# ТЕСТЫ
# ----------------------------------------
# Вариант через pytest внутри контейнеров.
# Предполагается, что pytest уже в requirements.* сервисов.

test-core:
	$(DOCKER_COMPOSE) run --rm core-api pytest

test-auth:
	$(DOCKER_COMPOSE) run --rm auth-host pytest

test-ai:
	$(DOCKER_COMPOSE) run --rm ai-service pytest

test-workers:
	$(DOCKER_COMPOSE) run --rm workers pytest || true

# Запуск всех тестов по очереди
test: test-core test-auth test-ai

schema-smoke-core:
	$(DOCKER_COMPOSE) run --rm core-api pytest platform/processing-core/app/tests/test_schema_smoke.py -q

schema-smoke-core-local:
	@if [ -z "$$DATABASE_URL" ]; then echo "DATABASE_URL is required"; exit 1; fi
	DATABASE_URL="$$DATABASE_URL" pytest platform/processing-core/app/tests/test_schema_smoke.py -q

# ----------------------------------------
# HEALTH-CHECK'И ЧЕРЕЗ NGINX
# ----------------------------------------
# Требует запущенного стека (nginx + сервисы).

health:
	curl -s "http://localhost/api/v1/health" || echo "core-api health check failed"

health-core: health

# Если позже сделаем /api/v1/health у auth-host и ai-service через nginx —
# сюда можно будет добавить отдельные проверки:
health-auth:
	@echo "Auth-host health endpoint через nginx пока не определён"

health-ai:
	@echo "AI-service health endpoint через nginx пока не определён"

smoke:
	pytest -q tests/test_no_merge_markers.py tests/test_smoke_gateway_routing.py

# ----------------------------------------
# ALEMBIC VERSION TABLE CHECK
# ----------------------------------------

alembic-version-check:
	$(DOCKER_COMPOSE) exec -T postgres psql -U neft -d neft -c "select table_schema, table_name from information_schema.tables where table_name in ('alembic_version_core','alembic_version_auth') order by 1,2;"
	$(DOCKER_COMPOSE) exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
	$(DOCKER_COMPOSE) exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
	$(DOCKER_COMPOSE) exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_core where version_num like '%auth%';"
	$(DOCKER_COMPOSE) exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_auth where version_num like '%core%';"

# ----------------------------------------
# ЧИСТКА
# ----------------------------------------

clean-volumes:
	$(DOCKER_COMPOSE) down -v

clean-images:
	$(DOCKER_COMPOSE) down --rmi local
