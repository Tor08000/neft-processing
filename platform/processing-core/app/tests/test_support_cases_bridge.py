from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.cases import CaseComment, CaseQueue, CaseStatus
from app.models.support_ticket import SupportTicket, SupportTicketPriority, SupportTicketStatus
from app.services.support_cases import get_support_ticket_case, sync_support_ticket_case, sync_support_ticket_comment
from app.tests._scoped_router_harness import SUPPORT_TICKET_TEST_TABLES, scoped_session_context


def test_support_ticket_case_bridge_syncs_lifecycle_and_comments():
    with scoped_session_context(tables=SUPPORT_TICKET_TEST_TABLES) as session:
        org_id = str(uuid4())
        ticket = SupportTicket(
            id="00000000-0000-0000-0000-000000000111",
            org_id=org_id,
            created_by_user_id="user-1",
            subject="Проблема с документом",
            message="Документ не подписывается",
            status=SupportTicketStatus.OPEN,
            priority=SupportTicketPriority.NORMAL,
        )
        session.add(ticket)
        session.flush()

        created_case = sync_support_ticket_case(
            session,
            ticket=ticket,
            tenant_id=1,
            client_id="client-1",
            actor_id="user-1",
        )
        assert created_case is not None
        assert str(created_case.id) == str(ticket.id)
        assert created_case.client_id == "client-1"
        assert created_case.queue == CaseQueue.SUPPORT
        assert created_case.status == CaseStatus.TRIAGE
        assert created_case.case_source_ref_type == "SUPPORT_TICKET"

        comment_at = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
        comment = sync_support_ticket_comment(
            session,
            ticket=ticket,
            author="user-1",
            body="Прикрепил дополнительное описание",
            occurred_at=comment_at,
        )
        assert comment is not None
        session.flush()
        assert (
            session.query(CaseComment)
            .filter(CaseComment.case_id == created_case.id)
            .filter(CaseComment.body == "Прикрепил дополнительное описание")
            .count()
            == 1
        )

        ticket.status = SupportTicketStatus.CLOSED
        ticket.updated_at = datetime(2026, 4, 13, 12, 30, tzinfo=timezone.utc)
        ticket.resolved_at = ticket.updated_at
        session.add(ticket)
        session.flush()

        sync_support_ticket_case(
            session,
            ticket=ticket,
            tenant_id=1,
            client_id="client-1",
            actor_id="user-1",
        )

        updated_case = get_support_ticket_case(session, ticket_id=str(ticket.id))
        assert updated_case is not None
        assert updated_case.status == CaseStatus.CLOSED
