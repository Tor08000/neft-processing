import importlib


def test_client_cards_single_mapping_source():
    app_module = importlib.import_module("app.main")
    assert app_module.app is not None

    canonical = importlib.import_module("app.models.client_cards")
    portal_models = importlib.import_module("app.models.client_portal")
    entitlements_service = importlib.import_module("app.services.entitlements_service")

    assert canonical.ClientCard is portal_models.ClientCard
    assert canonical.ClientCard is entitlements_service.ClientCard
