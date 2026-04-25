from sqlalchemy import String

from app.models.fleet import ClientEmployee, FuelCardGroupMember, FuelGroupAccess


def test_fleet_membership_tables_match_varchar_storage_truth() -> None:
    member_columns = FuelCardGroupMember.__table__.c
    access_columns = FuelGroupAccess.__table__.c
    employee_columns = ClientEmployee.__table__.c

    assert isinstance(member_columns.group_id.type, String)
    assert isinstance(member_columns.card_id.type, String)
    assert isinstance(access_columns.id.type, String)
    assert isinstance(access_columns.group_id.type, String)
    assert isinstance(access_columns.employee_id.type, String)
    assert isinstance(employee_columns.id.type, String)
