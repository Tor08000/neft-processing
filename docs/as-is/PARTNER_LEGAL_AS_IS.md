# Partner Legal & Tax — AS-IS

## Overview

В контуре **Partner Legal & Tax** платформа хранит юридический профиль партнёра, фиксирует налоговую классификацию и блокирует выплаты до подтверждения профиля. Контур предназначен для соблюдения требований комплаенса и подготовки документов для выплат.

## Data model

### partner_legal_profiles
* `partner_id` — идентификатор партнёра (FK на org/partner контекст).
* `legal_type` — тип партнёра: `INDIVIDUAL`, `IP`, `LEGAL_ENTITY`.
* `country`, `tax_residency` — юрисдикции.
* `tax_regime` — налоговый режим (`USN`, `OSNO`, `SELF_EMPLOYED`, `FOREIGN`, `OTHER`).
* `vat_applicable`, `vat_rate` — НДС.
* `legal_status` — статус профиля: `DRAFT`, `PENDING_REVIEW`, `VERIFIED`, `BLOCKED`.

### partner_legal_details
* реквизиты: `legal_name`, `inn`, `kpp`, `ogrn`, `passport`, `bank_account`, `bank_bic`, `bank_name`.

### partner_tax_policies
Справочник налоговых режимов (read-only). Хранит ставки и комментарии. Нужен для информационной справки в документах и payout preview.

### partner_legal_packs
История сформированных юридических пакетов (PDF/ZIP + metadata).

## Enforcement on payouts

* **Hard block**: payout request доступен только если есть профиль, реквизиты заполнены и `legal_status = VERIFIED`.
* **Soft warnings**: логируется audit event при неподтверждённом налоговом режиме или изменении реквизитов в последние N дней (по умолчанию 3).

## Tax context

При генерации документов партнёра (invoices/acts) и payout preview добавляется блок:

```json
{
  "tax_context": {
    "legal_type": "IP",
    "tax_regime": "USN",
    "tax_rate": 6,
    "vat": false,
    "vat_rate": 0
  }
}
```

## APIs

### Partner API
* `GET /api/core/partner/legal/profile` — текущий юридический профиль + чеклист.
* `PUT /api/core/partner/legal/profile` — заполнение профиля.
* `PUT /api/core/partner/legal/details` — заполнение реквизитов.
* `GET /api/core/partner/payouts/preview` — предварительный просмотр выплаты с налоговым контекстом.

### Admin API
* `GET /api/core/v1/admin/partners/{id}/legal-profile`
* `POST /api/core/v1/admin/partners/{id}/legal-profile/status`
* `POST /api/core/v1/admin/partners/{id}/legal-pack`
* `GET /api/core/v1/admin/partners/{id}/legal-pack/history`

## E2E smoke

Сценарий закреплён в скрипте:
* `scripts/smoke_partner_legal_payout_e2e.cmd`
