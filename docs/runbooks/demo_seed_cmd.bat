@echo off
setlocal enableextensions enabledelayedexpansion

set "BASE_URL=http://localhost/api/v1"
set "CLIENT_RESP=%TEMP%\neft_client.json"
set "MERCHANT_RESP=%TEMP%\neft_merchant.json"
set "TERMINAL_RESP=%TEMP%\neft_terminal.json"
set "CARD_RESP=%TEMP%\neft_card.json"
set "AUTH_RESP=%TEMP%\neft_authorize.json"

if exist "%CLIENT_RESP%" del "%CLIENT_RESP%"
if exist "%MERCHANT_RESP%" del "%MERCHANT_RESP%"
if exist "%TERMINAL_RESP%" del "%TERMINAL_RESP%"
if exist "%CARD_RESP%" del "%CARD_RESP%"
if exist "%AUTH_RESP%" del "%AUTH_RESP%"

echo Creating client...
curl -s -X POST %BASE_URL%/clients -H "Content-Type: application/json" --data-raw "{\"name\":\"CLIENT-1\"}" > "%CLIENT_RESP%"
for /f "delims=" %%i in ('python -c "import json,sys;print(json.load(open(r'%CLIENT_RESP%'))['id'])"') do set "CLIENT_ID=%%i"

echo Client ID: %CLIENT_ID%
echo Client response:
type "%CLIENT_RESP%"

echo Creating merchant...
curl -s -X POST %BASE_URL%/merchants -H "Content-Type: application/json" --data-raw "{\"id\":\"MERCHANT-1\",\"name\":\"MERCHANT-1\",\"status\":\"ACTIVE\"}" > "%MERCHANT_RESP%"
echo Merchant response:
type "%MERCHANT_RESP%"

echo Creating terminal...
curl -s -X POST %BASE_URL%/terminals -H "Content-Type: application/json" --data-raw "{\"id\":\"TERM-1\",\"merchant_id\":\"MERCHANT-1\",\"status\":\"ACTIVE\",\"location\":\"MSK\"}" > "%TERMINAL_RESP%"
echo Terminal response:
type "%TERMINAL_RESP%"

echo Creating card...
curl -s -X POST %BASE_URL%/cards -H "Content-Type: application/json" --data-raw "{\"id\":\"CARD-1\",\"client_id\":\"%CLIENT_ID%\",\"status\":\"ACTIVE\"}" > "%CARD_RESP%"
echo Card response:
type "%CARD_RESP%"

echo Authorizing transaction...
curl -s -X POST %BASE_URL%/transactions/authorize -H "Content-Type: application/json" --data-raw "{\"client_id\":\"%CLIENT_ID%\",\"card_id\":\"CARD-1\",\"terminal_id\":\"TERM-1\",\"merchant_id\":\"MERCHANT-1\",\"amount\":10000,\"currency\":\"RUB\",\"ext_operation_id\":\"EXT-0001\"}" > "%AUTH_RESP%"
echo Authorize response:
type "%AUTH_RESP%"

echo.
echo Demo seed complete. Client ID: %CLIENT_ID%
endlocal
