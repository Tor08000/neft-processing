# Portal Shell Acceptance — Sprint A Checklist

> 10-point verification checklist with commands for the unified portal shell scope.

## 1) Portal entrypoint reachable
- **Check:** `/portal/` отвечает и не даёт 404/white screen.
- **Command:** `curl -i http://localhost/portal/`

## 2) Client deep link redirect → portal
- **Check:** `/client/cards` редиректит на эквивалентный путь внутри portal.
- **Command:** `curl -i http://localhost/client/cards`

## 3) Partner deep link redirect → portal
- **Check:** `/partner/orders` редиректит на эквивалентный путь внутри portal.
- **Command:** `curl -i http://localhost/partner/orders`

## 4) Deep link сохраняет query params
- **Check:** query-параметры сохраняются при редиректе.
- **Command:** `curl -i "http://localhost/client/cards?tab=active&limit=20"`

## 5) Единственный bootstrap вызов
- **Check:** в Network только `GET /api/core/portal/me`.
- **Command:** `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/portal/me`

## 6) Legacy wrappers доступны
- **Check:** `/api/core/client/me` и `/api/core/partner/me` возвращают совместимый subset.
- **Command:** `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/me`

## 7) Auth guard error pages
- **Check:** 401 показывает UnauthorizedPage (единый экран).
- **Command:** `curl -i http://localhost/portal/whatever`

## 8) Capability-driven navigation
- **Check:** пункты меню отображаются только при наличии capability.
- **Command:** `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/portal/me`

## 9) Route gating screen
- **Check:** при отсутствии capability открывается Paywall/ComingSoon (не 404).
- **Command:** `curl -i http://localhost/portal/partner/orders`

## 10) verify_all включает portal smoke
- **Check:** общий verify запускает `smoke_portal_unification_e2e.cmd`.
- **Command:** `scripts\verify_all.cmd`
