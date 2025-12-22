# Scripts

- `smoke_local.sh` — быстрый smoke-check запущенного docker-compose стенда: таблица
  `merchants` есть в Postgres, а gateway и SPA отдают ожидаемые ответы на локальных
  /health, /admin/ и /client/.
- `smoke_invoice_state_machine.cmd` — Windows CMD smoke: логин, генерация счета, переходы
  ISSUED/SENT/PAID, попытка запрещенного rollback, платежи и финальная проверка статуса
  инвойса и due/paid значений.
