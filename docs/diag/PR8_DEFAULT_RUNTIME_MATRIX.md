# PR-8 Default Runtime Matrix
Автогенерация: `python scripts/diag/dump_runtime_matrix.py`.

Критерии риска:
- `SAFE` — дефолт real/prod/non-mock.
- `RISK` — дефолт содержит mock/stub/placeholder.
- `UNKNOWN` — дефолт статически не извлечён.

| Service | Setting key | Default | Allowed values | Where defined | Overridden in compose? | Compose value | Risk |
|---|---|---|---|---|---|---|---|
| document-service | PROVIDER_X_MODE | mock | mock, prod | platform/document-service/app/settings.py:24 `provider_x_mode: str = os.getenv("PROVIDER_X_MODE", "mock")` | false |  | RISK |
| integration-hub | APP_ENV | prod | dev, test, prod, production | platform/integration-hub/neft_integration_hub/settings.py:14 `app_env: str = os.getenv("APP_ENV", "prod").lower()` | true | ${APP_ENV:-prod} | SAFE |
| integration-hub | DIADOK_MODE | mock | mock, prod | platform/integration-hub/neft_integration_hub/settings.py:41 `diadok_mode: str = os.getenv("DIADOK_MODE", "mock")` | false |  | RISK |
| integration-hub | EMAIL_PROVIDER_MODE | mock | mock, smtp, integration_hub, stub, disabled | platform/integration-hub/neft_integration_hub/settings.py:67 `email_provider_mode: str = os.getenv("EMAIL_PROVIDER_MODE", "mock").lower()` | false |  | RISK |
| integration-hub | NOTIFICATIONS_MODE | mock | mock, real | platform/integration-hub/neft_integration_hub/settings.py:64 `notifications_mode: str = os.getenv("NOTIFICATIONS_MODE", "mock").lower()` | false |  | RISK |
| integration-hub | OTP_PROVIDER_MODE | prod | mock, prod | platform/integration-hub/neft_integration_hub/settings.py:59 `otp_provider_mode: str = os.getenv("OTP_PROVIDER_MODE", "prod").lower()` | false |  | SAFE |
| logistics-service | APP_ENV | prod | dev, test, prod, production | platform/logistics-service/neft_logistics_service/settings.py:15 `app_env: str = os.getenv("APP_ENV", "prod").lower()` | true | dev | SAFE |
| logistics-service | LOGISTICS_PROVIDER | UNKNOWN | mock, integration_hub, osrm | platform/logistics-service/neft_logistics_service/settings.py:27 `configured_provider = os.getenv("LOGISTICS_PROVIDER")` | true | mock | UNKNOWN |
| processing-core | APP_ENV | prod | dev, test, prod, production | shared/python/neft_shared/settings.py:29 `APP_ENV: str = os.getenv("APP_ENV", "prod").lower()` | true | dev | SAFE |
| processing-core | SMS_PROVIDER | sms_stub | sms_stub, real | shared/python/neft_shared/settings.py:254 `SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "sms_stub")` | false |  | RISK |
| processing-core | VOICE_PROVIDER | voice_stub | voice_stub, real | shared/python/neft_shared/settings.py:255 `VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "voice_stub")` | false |  | RISK |
