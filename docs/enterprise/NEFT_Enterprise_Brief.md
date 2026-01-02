# NEFT Enterprise Brief (One Page)

## Problem

Enterprise-команды сталкиваются с тремя системными проблемами:

- решения трудно объяснить внешнему аудитору;
- невозможно восстановить контекст принятия решений;
- человеческий фактор не контролируется на уровне системной трассировки.

## Solution

NEFT Platform фиксирует все этапы решения в виде объяснимых снимков и событий:

- Explain/Diff/Actions сохраняются как snapshot’ы;
- любые изменения в кейсе становятся частью hash-chain;
- события подписываются сервером и проверяются независимым verify.

## Why it’s different

- WORM для ключевой аудит-единицы (`case_events`).
- Hash-chain в audit_log + детерминированная верификация.
- Редакция PII/секретов до хранения и экспорта.

## Trust & Audit

- verify endpoints:
  - `/api/v1/audit/verify`
  - `/cases/{case_id}/events/verify`
- signed URLs для экспортов.
- purge экспорта фиксируется в `audit_purge_log`.

## Typical Use Cases

- Enterprise risk & compliance (финансовые операции, лимиты, блокировки).
- Logistics / Energy / Gov-adjacent: расследования и проверка цепочки событий.
- Подготовка due diligence и внешнего аудита.
