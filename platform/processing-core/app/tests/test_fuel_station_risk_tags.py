from types import SimpleNamespace

from app.services.fuel.authorize import _station_risk_tags


def test_station_risk_tags_mapping() -> None:
    assert _station_risk_tags(SimpleNamespace(risk_zone=None)) == []
    assert _station_risk_tags(SimpleNamespace(risk_zone="GREEN")) == []
    assert _station_risk_tags(SimpleNamespace(risk_zone="YELLOW")) == ["STATION_RISK_YELLOW"]
    assert _station_risk_tags(SimpleNamespace(risk_zone="RED")) == ["STATION_RISK_RED"]
