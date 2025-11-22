
---

## 2. `docs/RUNBOOKS/deploy-prod.md`

```markdown
# Runbook: Production Deploy NEFT Processing

## 1. Назначение

Этот документ описывает, как выкатывать новую версию NEFT Processing (core-api, auth-host, ai-service, workers, nginx) в прод-среду:

- подготовка к деплою;
- порядок действий;
- применение миграций;
- проверки после;
- базовый rollback.

---

## 2. Предусловия

- Репозиторий `neft-processing` обновлён (`git pull`).
- На сервере есть:
  - Docker
  - Docker Compose
- Переменные окружения заданы в `.env` (скопировано из `.env.example` и настроено).
- Постгрес и Редис уже развернуты и используются системой.

---

## 3. Подготовка

### 3.1. Обновить код

```bash
cd /path/to/neft-processing
git pull
