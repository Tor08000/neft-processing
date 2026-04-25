from uuid import UUID

from app.routers.admin.crm import router as admin_crm_router
from app.security.rbac.principal import Principal, get_principal
from app.tests._crm_test_harness import CRM_TEST_HEADERS, crm_admin_client_context, crm_session_context
from app.tests._scoped_router_harness import router_client_context


def _principal_for_roles(*roles: str) -> Principal:
    return Principal(
        user_id=UUID("00000000-0000-0000-0000-000000000010"),
        roles=set(),
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=False,
        raw_claims={"roles": list(roles)},
    )


def _crm_client_for_roles(session, *roles: str):
    return router_client_context(
        router=admin_crm_router,
        prefix="/api/core/v1/admin",
        db_session=session,
        dependency_overrides={get_principal: lambda: _principal_for_roles(*roles)},
    )


def test_crm_tariff_crud():
    with crm_session_context() as session:
        with crm_admin_client_context(db_session=session) as client:
            create_resp = client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_BASIC",
                    "name": "Fuel Basic",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 10000,
                    "currency": "RUB",
                    "features": {"fuel": True, "risk": True},
                },
                headers=CRM_TEST_HEADERS,
            )
            assert create_resp.status_code == 200

            list_resp = client.get("/api/core/v1/admin/crm/tariffs", headers=CRM_TEST_HEADERS)
            assert list_resp.status_code == 200
            assert list_resp.json()[0]["id"] == "FUEL_BASIC"


def test_crm_tariffs_follow_admin_capability_roles():
    with crm_session_context() as session:
        with crm_admin_client_context(db_session=session) as admin_client:
            admin_client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "FUEL_BASIC",
                    "name": "Fuel Basic",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 10000,
                    "currency": "RUB",
                    "features": {"fuel": True},
                },
                headers=CRM_TEST_HEADERS,
            )

        with _crm_client_for_roles(session, "NEFT_SALES") as sales_client:
            response = sales_client.get("/api/core/v1/admin/crm/tariffs", headers=CRM_TEST_HEADERS)
            assert response.status_code == 200
            assert response.json()[0]["id"] == "FUEL_BASIC"

        with _crm_client_for_roles(session, "OBSERVER") as observer_client:
            list_response = observer_client.get("/api/core/v1/admin/crm/tariffs", headers=CRM_TEST_HEADERS)
            assert list_response.status_code == 200

            create_response = observer_client.post(
                "/api/core/v1/admin/crm/tariffs",
                json={
                    "id": "OBSERVER_WRITE",
                    "name": "Observer write",
                    "status": "ACTIVE",
                    "billing_period": "MONTHLY",
                    "base_fee_minor": 1,
                    "currency": "RUB",
                },
                headers=CRM_TEST_HEADERS,
            )
            assert create_response.status_code == 403
            assert create_response.json()["detail"]["reason"] == "missing_admin_crm_capability"
