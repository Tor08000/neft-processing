# Portal Unification — AS-IS

## Summary

- Client Portal и Partner Portal — отдельные фронтенды и bootstrap-флоу.
- `/api/core/client/me` используется для клиентского bootstrap, partner-профиль читается отдельно из auth-host (`/api/auth/v1/auth/me`).
- Entitlements v2 не содержит `org.roles` и `capabilities` как часть snapshot.
- Billing enforcement применяется только в клиентских потоках и не влияет на partner-функции на уровне capability-слоя.

## Current Entry Points

- Client bootstrap: `GET /api/core/client/me`.
- Partner bootstrap: `GET /api/auth/v1/auth/me` (auth-host), далее отдельные partner endpoints.
- Нет единого SSoT `/portal/me`.

## Access Model

- Доступ строится отдельно по client/partner ролям пользователя.
- Организационные роли (CLIENT/PARTNER) не хранятся как единый массив в org scope.
- Entitlements snapshot не формирует единый список возможностей (capabilities).

## UX последствия

- Меню клиентского и партнёрского порталов формируется по разным правилам.
- При появлении новой роли (partner/client) требуется переключение портала, а не автоматическая активация секций.
