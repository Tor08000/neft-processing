from sqlalchemy import String

from app.models.crm import ClientOnboardingEvent, CRMDeal, CRMDealEvent, CRMLead, CRMTask, CRMTicketLink


def test_crm_onboarding_tables_match_varchar_storage_truth() -> None:
    lead_columns = CRMLead.__table__.c
    deal_columns = CRMDeal.__table__.c
    deal_event_columns = CRMDealEvent.__table__.c
    task_columns = CRMTask.__table__.c
    ticket_link_columns = CRMTicketLink.__table__.c
    onboarding_event_columns = ClientOnboardingEvent.__table__.c

    assert isinstance(lead_columns.id.type, String)
    assert isinstance(deal_columns.id.type, String)
    assert isinstance(deal_columns.lead_id.type, String)
    assert isinstance(deal_event_columns.id.type, String)
    assert isinstance(deal_event_columns.deal_id.type, String)
    assert isinstance(task_columns.id.type, String)
    assert isinstance(ticket_link_columns.id.type, String)
    assert isinstance(onboarding_event_columns.id.type, String)
