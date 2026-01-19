# Sprint A — Admin Shell & Safety (Acceptance)

## Запуск Admin UI

1. Убедитесь, что gateway и core-api запущены.
2. Запуск фронтенда (admin-ui):
   ```bash
   cd frontends/admin-ui
   npm install
   npm run dev
   ```
3. Откройте `http://localhost/admin/`.

## Получение admin token

Используйте скрипт:

```cmd
scripts\get_admin_token.cmd
```

Скрипт выведет bearer токен (используется для `Authorization: Bearer <token>`).

## Smoke tests (Windows CMD)

```cmd
scripts\smoke_admin_shell.cmd
```

Лог сохраняется в `logs/smoke_admin_shell_*.log`.

## Критерии принятия (Sprint A)

- Admin UI загружается только после успешного `/api/core/v1/admin/me`.
- RBAC работает:
  - пункты меню скрываются при отсутствии `read` permissions;
  - прямой URL без прав отдаёт 403 страницу.
- Status pages отрабатывают (401/403/404/crash).
- Единый modal подтверждения write-действий существует (confirm + reason).
- Smoke script `scripts/smoke_admin_shell.cmd` выдаёт PASS.
