# NEFT Processing — Agent Rules

## цель
Агент доводит задачи до состояния "готово к PR" без нарушения архитектуры.

---

## структура проекта

- platform/processing-core → backend (FastAPI)
- platform/auth-host → low-latency сервис (НЕ ТРОГАТЬ без указания)
- frontends/client-portal → клиентский кабинет
- frontends/admin-ui → админка
- gateway → API gateway (ОСТОРОЖНО)

---

## разрешено менять

- frontends/**
- platform/processing-core/app/**
- tests
- docs

---

## запрещено без явного указания

- billing / clearing логика
- auth-host
- security / JWT
- gateway публичные маршруты
- удаление таблиц/полей

---

## команды проверки

frontend:
cd frontends/client-portal && npm run build
cd frontends/client-portal && npx vitest run

backend:
cd platform/processing-core && pytest

---

## definition of done

- код собирается
- тесты проходят
- нет регресса существующего функционала
- PR содержит summary

---

## правила

- не переписывать тесты под баг
- не менять лишние файлы
- минимальные изменения лучше больших
- если задача выходит за рамки — остановиться