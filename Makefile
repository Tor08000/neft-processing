SHELL := /bin/bash

# Можно переопределить переменную в CI, если надо:
# DOCKER_COMPOSE="docker-compose"
DOCKER_COMPOSE ?= docker compose

PROJECT_NAME := neft-processing

.PHONY: up down restart ps build prepull-base-images \
        logs logs-core logs-auth logs-workers logs-nginx logs-ai logs-db \
        shell-core shell-auth shell-workers shell-ai \
        migrate test test-core test-auth test-ai test-workers \
        health health-core health-auth health-ai prometheus-smoke smoke schema-smoke-core \
        schema-smoke-core-local alembic-version-check \
        clean-volumes clean-images kpi-smoke cases-smoke subscription-smoke plans-smoke

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

prometheus-smoke:
	$(DOCKER_COMPOSE) exec -T prometheus sh -lc 'set -e; \
targets="gateway 80 /metrics \
core-api 8000 /metrics \
auth-host 8000 /api/v1/metrics \
ai-service 8000 /metrics \
crm-service 8000 /metrics \
logistics-service 8000 /metrics \
document-service 8000 /metrics \
celery-exporter 9808 /metrics"; \
echo "$$targets" | while read -r host port path; do \
  [ -z "$$host" ] && continue; \
  echo "checking $$host:$$port$$path"; \
  getent hosts "$$host" >/dev/null; \
  wget -qO- "http://$$host:$$port$$path" >/dev/null; \
done'

smoke:
	pytest -q tests/test_no_merge_markers.py tests/test_smoke_gateway_routing.py

kpi-smoke:
	curl "http://localhost:8001/api/core/kpi/summary?window_days=7"
	curl "http://localhost:8001/api/core/achievements/summary?window_days=7"

cases-smoke:
	@if [ -z "$$CASES_TOKEN" ]; then echo "CASES_TOKEN is required"; exit 1; fi
	curl -s -X POST "http://localhost/api/core/cases" \
	  -H "Authorization: Bearer $$CASES_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d '{"kind":"operation","entity_id":"op_123","priority":"MEDIUM","note":"smoke case","explain":{"decision":"DECLINE","score":82},"diff":{"score_diff":{"risk_before":0.82,"risk_after":0.47}},"selected_actions":[{"code":"REQUEST_DOCS","what_if":{"impact":0.1}}]}' | cat
	curl -s -X GET "http://localhost/api/core/cases?limit=5" \
	  -H "Authorization: Bearer $$CASES_TOKEN" | cat

cases-escalation-smoke:
	@if [ -z "$$CASES_TOKEN" ]; then echo "CASES_TOKEN is required"; exit 1; fi
	@case_id=$$(curl -s -X POST "http://localhost/api/core/cases" \
	  -H "Authorization: Bearer $$CASES_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d '{"kind":"operation","entity_id":"op_456","priority":"MEDIUM","note":"escalation smoke","explain":{"decision":"DECLINE","reason_codes":["velocity_high"]}}' | jq -r '.id'); \
	echo "case_id=$$case_id"; \
	curl -s -X GET "http://localhost/api/core/cases/$$case_id" \
	  -H "Authorization: Bearer $$CASES_TOKEN" | cat

subscription-smoke:
	@if [ -z "$$SUBSCRIPTIONS_CLIENT_TOKEN" ]; then echo "SUBSCRIPTIONS_CLIENT_TOKEN is required"; exit 1; fi
	curl -s -X GET "http://localhost/api/core/subscriptions/me" \
	  -H "Authorization: Bearer $$SUBSCRIPTIONS_CLIENT_TOKEN" | cat

plans-smoke:
	@if [ -z "$$SUBSCRIPTIONS_ADMIN_TOKEN" ]; then echo "SUBSCRIPTIONS_ADMIN_TOKEN is required"; exit 1; fi
	@if [ -z "$$SUBSCRIPTIONS_CLIENT_ID" ]; then echo "SUBSCRIPTIONS_CLIENT_ID is required"; exit 1; fi
	@plan_id=$$(curl -s -X POST "http://localhost/api/core/subscriptions/plans" \
	  -H "Authorization: Bearer $$SUBSCRIPTIONS_ADMIN_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d '{"code":"BASIC","title":"BASIC","description":"Smoke plan","is_active":true,"billing_period_months":1,"price_cents":10000,"currency":"RUB"}' | jq -r '.id'); \
	echo "plan_id=$$plan_id"; \
	curl -s -X PATCH "http://localhost/api/core/subscriptions/plans/$$plan_id/modules" \
	  -H "Authorization: Bearer $$SUBSCRIPTIONS_ADMIN_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d '[{"module_code":"FUEL_CORE","enabled":true,"tier":"basic","limits":{"cards_max":10}},{"module_code":"ANALYTICS","enabled":true,"tier":"basic","limits":{"dashboards":true}}]' | cat; \
	curl -s -X POST "http://localhost/api/core/admin/clients/$$SUBSCRIPTIONS_CLIENT_ID/subscription/assign" \
	  -H "Authorization: Bearer $$SUBSCRIPTIONS_ADMIN_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d "{\"plan_id\":\"$$plan_id\",\"duration_months\":1,\"auto_renew\":false}" | cat

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
