# On-call модель v1

## Роли
- **Primary:** engineer (дежурный инженер).
- **Secondary:** architect/owner.
- **Business contact:** optional.

## Alerting (Prometheus/Grafana/Alertmanager)
- Core API down
- Auth latency spike
- Billing job missed SLA
- No job execution evidence
- Document-service error rate
- EDO failure rate
- ERP reconciliation FAILED

## Escalation policy
- Кто отвечает: Primary → Secondary → Business contact.
- В какое время: 24/7 (TBD), расписание дежурств в календаре.
- Как эскалировать: Pager/Telegram/Call (TBD).
- Когда “будить”:
  - P0: простой Core API/Auth, потеря денег/документов.
  - P1: деградация > SLO, backlog jobs.
  - P2: рост ошибок без impact на деньги/документы.
