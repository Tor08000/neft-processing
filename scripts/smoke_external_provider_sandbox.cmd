@echo off
setlocal

if "%HUB_BASE%"=="" set "HUB_BASE=http://localhost:8005"
if "%INTEGRATION_HUB_INTERNAL_TOKEN%"=="" set "INTEGRATION_HUB_INTERNAL_TOKEN=change-me"

set "TMP_DIR=%~dp0_tmp\smoke_external_provider_sandbox"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1
set "PROVIDERS_FILE=%TMP_DIR%\providers.json"
set "OTP_1_FILE=%TMP_DIR%\otp_1.json"
set "OTP_2_FILE=%TMP_DIR%\otp_2.json"
set "EMAIL_FILE=%TMP_DIR%\email.json"
set "NOTIFICATIONS_FILE=%TMP_DIR%\notifications.json"
set "FUEL_FILE=%TMP_DIR%\fuel.json"
set "EVIDENCE_FILE=%~dp0..\docs\diag\external-provider-sandbox-proof-20260425.json"

call :curl_json "providers health" GET "%HUB_BASE%/api/int/v1/providers/health" "" "%PROVIDERS_FILE%" 200 || exit /b 1
call :curl_json "otp sandbox first" POST "%HUB_BASE%/api/int/v1/otp/send" "{\"channel\":\"sms\",\"destination\":\"+79990000000\",\"message\":\"1234\",\"idempotency_key\":\"sandbox-otp-20260425\",\"meta\":{\"source\":\"smoke\"}}" "%OTP_1_FILE%" 200 || exit /b 1
call :curl_json "otp sandbox replay" POST "%HUB_BASE%/api/int/v1/otp/send" "{\"channel\":\"sms\",\"destination\":\"+79990000000\",\"message\":\"1234\",\"idempotency_key\":\"sandbox-otp-20260425\",\"meta\":{\"source\":\"smoke\"}}" "%OTP_2_FILE%" 200 || exit /b 1
call :curl_json "email sandbox" POST "%HUB_BASE%/api/int/notify/email/send" "{\"to\":\"sandbox@example.com\",\"subject\":\"Sandbox\",\"text\":\"ok\",\"meta\":{\"source\":\"smoke\"}}" "%EMAIL_FILE%" 200 || exit /b 1
call :curl_json "notifications sandbox" POST "%HUB_BASE%/api/int/v1/notifications/send" "{\"channel\":\"email\",\"template\":\"sandbox\",\"to\":\"sandbox@example.com\",\"variables\":{\"source\":\"smoke\"}}" "%NOTIFICATIONS_FILE%" 200 || exit /b 1
call :curl_json "fuel provider sandbox" POST "%HUB_BASE%/v1/logistics/fuel/consumption" "{\"trip_id\":\"sandbox-trip\",\"distance_km\":123.4,\"vehicle_kind\":\"truck\",\"idempotency_key\":\"sandbox-fuel-20260425\"}" "%FUEL_FILE%" 200 || exit /b 1

python -c "import json, datetime as dt; from pathlib import Path; files={'providers':r'%PROVIDERS_FILE%','otp_1':r'%OTP_1_FILE%','otp_2':r'%OTP_2_FILE%','email':r'%EMAIL_FILE%','notifications':r'%NOTIFICATIONS_FILE%','fuel':r'%FUEL_FILE%'}; data={k:json.load(open(v,encoding='utf-8')) for k,v in files.items()}; providers={p.get('provider'):p for p in data['providers'].get('providers',[])}; required=['diadok','sbis','smtp_email','otp_sms','notifications','bank_api','erp_1c','fuel_provider','logistics_provider']; bad=[name for name in required if providers.get(name,{}).get('status')!='CONFIGURED' or providers.get(name,{}).get('sandbox_proof') is not True]; assert not bad, bad; assert data['otp_1']['mode']=='sandbox' and data['otp_2']['provider_message_id']==data['otp_1']['provider_message_id']; assert data['email']['mode']=='sandbox' and data['email']['status']=='sent'; assert data['notifications']['mode']=='sandbox' and data['notifications']['status']=='accepted'; assert data['fuel']['provider_mode']=='sandbox' and data['fuel']['sandbox_proof']['contract']=='fuel_consumption.v1'; evidence={'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'external-provider-sandbox-proof','classification':'VERIFIED_RUNTIME','providers':providers,'runtime_results':{k:data[k] for k in ['otp_1','otp_2','email','notifications','fuel']},'commands':['scripts\\smoke_external_provider_sandbox.cmd']}; Path(r'%EVIDENCE_FILE%').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8'); print('PASS external provider sandbox proof', r'%EVIDENCE_FILE%')" || exit /b 1

exit /b 0

:curl_json
set "LABEL=%~1"
set "METHOD=%~2"
set "URL=%~3"
set "BODY=%~4"
set "OUT=%~5"
set "EXPECTED=%~6"
set "CODE="
if "%BODY%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -H "X-Internal-Token: %INTEGRATION_HUB_INTERNAL_TOKEN%" "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -H "X-Internal-Token: %INTEGRATION_HUB_INTERNAL_TOKEN%" -H "Content-Type: application/json" -X %METHOD% -d "%BODY%" "%URL%"`) do set "CODE=%%c"
)
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
type "%OUT%"
exit /b 1
