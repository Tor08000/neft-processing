from __future__ import annotations


def test_contacts_crud(client, tenant_headers):
    create = client.post(
        "/api/v1/crm/contacts",
        headers=tenant_headers,
        json={"full_name": "Ivan Ivanov", "email": "ivan@example.com", "client_id": "c1"},
    )
    assert create.status_code == 200
    contact_id = create.json()["id"]

    listed = client.get("/api/v1/crm/contacts", headers=tenant_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patch = client.patch(f"/api/v1/crm/contacts/{contact_id}", headers=tenant_headers, json={"phone": "+7999"})
    assert patch.status_code == 200
    assert patch.json()["phone"] == "+7999"

    deleted = client.delete(f"/api/v1/crm/contacts/{contact_id}", headers=tenant_headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
