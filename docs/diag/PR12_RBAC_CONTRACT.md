# PR-12 — RBAC Contract Suite (200/403 proofs, no Docker)

Тесты выполняются как pure-python контрактные проверки guard/dependency функций без поднятия HTTP-сервера.

## Матрица endpoint → роль → ожидаемый статус → где проверяется

| Endpoint / guard contract | Роль/контекст | Ожидаемый статус | Где проверяется в тестах | Код guard/dependency |
|---|---|---:|---|---|
| `auth-host /v1/admin/users` через `_require_admin` | `PLATFORM_ADMIN` | 200 (allow) | `platform/auth-host/app/tests/test_rbac_contract.py::test_admin_endpoint_allows_platform_admin` | `platform/auth-host/app/api/routes/admin_users.py::_require_admin` |
| `auth-host /v1/admin/users` через `_require_admin` | `CLIENT_USER` | 403 | `...::test_admin_endpoint_denies_client_role` | `platform/auth-host/app/api/routes/admin_users.py::_require_admin` |
| `auth-host /v1/admin/users` через `_require_admin` | `PARTNER_USER` | 403 | `...::test_admin_endpoint_denies_partner_role` | `platform/auth-host/app/api/routes/admin_users.py::_require_admin` |
| `auth-host protected dependency` | пустые credentials | 401 | `...::test_protected_dependency_rejects_missing_credentials` | `platform/auth-host/app/api/routes/admin_users.py::_require_admin` |
| `auth-host protected dependency` | неправильная схема (`Basic`) | 401 | `...::test_protected_dependency_rejects_wrong_auth_scheme` | `platform/auth-host/app/api/routes/admin_users.py::_require_admin` |
| `auth-host protected dependency` | invalid token | 401 | `...::test_protected_dependency_rejects_invalid_token` | `platform/auth-host/app/security/__init__.py::decode_access_token` |
| `processing-core /api/core/client/me` guard (`verify_client_token`) | `CLIENT_USER + client_id` | 200 (allow) | `platform/processing-core/app/tests/test_rbac_contract.py::test_client_guard_allows_client_me` | `platform/processing-core/app/services/client_auth.py::verify_client_token` |
| `processing-core /api/core/client/me` guard (`verify_client_token`) | `PARTNER_USER` | 403 | `...::test_client_guard_denies_partner_token` | `platform/processing-core/app/services/client_auth.py::verify_client_token` |
| `processing-core /api/core/partner/me` guard (`verify_partner_token`) | `PARTNER_* + partner_id` | 200 (allow) | `...::test_partner_guard_allows_partner_me` | `platform/processing-core/app/services/partner_auth.py::verify_partner_token` |
| `processing-core /api/core/partner/me` guard (`verify_partner_token`) | `CLIENT_USER` | 403 | `...::test_partner_guard_denies_client_token` | `platform/processing-core/app/services/partner_auth.py::verify_partner_token` |
| `processing-core admin verify/me` guard (`verify_admin_token`) | `PLATFORM_ADMIN` | 200 (allow) | `...::test_admin_guard_allows_admin_verify_me` | `platform/processing-core/app/services/admin_auth.py::verify_admin_token` |
| `processing-core admin path` guard (`verify_admin_token`) | non-admin role | 403 | `...::test_admin_guard_denies_non_admin` | `platform/processing-core/app/services/admin_auth.py::verify_admin_token` |
| scope (client/org) для заказа | `client_id=A`, order принадлежит `client_id=B` | 403-equivalent (`forbidden` domain error) | `...::test_scope_client_org_mismatch_is_denied` | `platform/processing-core/app/services/marketplace_orders_service.py::get_order_for_client` |
| scope (partner) для заказа | `partner_id=A`, order принадлежит `partner_id=B` | 403-equivalent (`forbidden` domain error) | `...::test_scope_partner_id_mismatch_is_denied` | `platform/processing-core/app/services/marketplace_orders_service.py::get_order_for_partner` |

## Примечания

- Scope-проверки присутствуют и проверяются на сервисном уровне (`MarketplaceOrdersService`) через доменную ошибку `forbidden`.
- Не используются заглушки вида `assert True`.
- Контрактные тесты не требуют Postgres/Docker и не поднимают HTTP-сервер.
