# Partner Legal Verification Runbook

## Цель
Верифицировать юридический профиль партнёра, чтобы выплаты были доступны и корректно документированы.

## Preconditions
* Админ с доступом к core admin API.
* Партнёр заполнил юридический профиль и реквизиты.

## Шаги в Admin UI
1. Откройте страницу **Partner Legal** (`/partners/legal`).
2. Введите `partner_id` и нажмите **Загрузить**.
3. Проверьте:
   * тип партнёра (`legal_type`);
   * налоговый режим (`tax_regime`);
   * реквизиты (ИНН/КПП/ОГРН/паспорт + банк);
4. Добавьте комментарий (опционально).
5. Нажмите **Подтвердить** — статус станет `VERIFIED`.

## Шаги через API

```http
GET /api/core/v1/admin/partners/{partner_id}/legal-profile
```

```http
POST /api/core/v1/admin/partners/{partner_id}/legal-profile/status
Content-Type: application/json

{
  "status": "VERIFIED",
  "comment": "Документы подтверждены"
}
```

## Генерация пакета документов

```http
POST /api/core/v1/admin/partners/{partner_id}/legal-pack
Content-Type: application/json

{
  "format": "ZIP"
}
```

История:
```http
GET /api/core/v1/admin/partners/{partner_id}/legal-pack/history
```

## Validation
* Payout request возвращает 201 (ранее — 403 LEGAL_NOT_VERIFIED).
* В payout preview присутствует `tax_context`.
