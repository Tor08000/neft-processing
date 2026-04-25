from app.tests._crm_test_harness import CRM_TEST_HEADERS, crm_admin_client_context, crm_session_context


def test_crm_clients_crud_and_filters():
    with crm_session_context() as session:
        with crm_admin_client_context(db_session=session) as client:
            payload = {
                "id": "crm-client-1",
                "tenant_id": 1,
                "legal_name": "ООО Ромашка",
                "tax_id": "7700000000",
                "country": "RU",
                "timezone": "Europe/Moscow",
                "status": "ACTIVE",
                "meta": {"segment": "enterprise"},
            }
            response = client.post("/api/core/v1/admin/crm/clients", json=payload, headers=CRM_TEST_HEADERS)
            assert response.status_code == 200
            assert response.json()["id"] == "crm-client-1"

            list_response = client.get(
                "/api/core/v1/admin/crm/clients",
                params={"status": "ACTIVE", "search": "Ромашка"},
                headers=CRM_TEST_HEADERS,
            )
            assert list_response.status_code == 200
            assert [item["id"] for item in list_response.json()] == ["crm-client-1"]

            update_response = client.patch(
                "/api/core/v1/admin/crm/clients/crm-client-1",
                json={"status": "SUSPENDED"},
                headers=CRM_TEST_HEADERS,
            )
            assert update_response.status_code == 200
            assert update_response.json()["status"] == "SUSPENDED"
