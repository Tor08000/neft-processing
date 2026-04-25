from sqlalchemy import String

from app.models.abac import AbacPolicy, AbacPolicyVersion


def test_abac_models_match_varchar_id_storage_truth():
    assert isinstance(AbacPolicyVersion.__table__.c.id.type, String)
    assert isinstance(AbacPolicy.__table__.c.id.type, String)
    assert isinstance(AbacPolicy.__table__.c.version_id.type, String)
