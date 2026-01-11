from app.db import Base
import app.models  # noqa: F401


def test_security_tables_registered_once() -> None:
    table_names = list(Base.metadata.tables)
    assert table_names.count("service_identities") == 1
    assert table_names.count("service_tokens") == 1
    assert table_names.count("service_token_audit") == 1
    assert table_names.count("abac_policy_versions") == 1
    assert table_names.count("abac_policies") == 1
