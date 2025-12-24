@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==============================
REM  НАСТРОЙКИ
REM ==============================
set "BASE_URL=http://localhost:8001"
set "REQ_FILE=req.json"

if not exist "%REQ_FILE%" (
  echo [ERROR] Файл запроса "%REQ_FILE%" не найден.
  exit /b 1
)

echo ==============================================
echo   NEFT Processing - тестовый прогон операций
echo ==============================================
echo.

REM ==============================
REM  TEST 1: AUTH -> CAPTURE -> FULL REFUND
REM ==============================
echo [TEST 1] AUTH -> CAPTURE -> FULL REFUND
call :auth AUTH1_ID
call :capture %AUTH1_ID% 5000 CAPTURE1_ID
call :refund_full %CAPTURE1_ID% full_refund_1
echo.

REM ==============================
REM  TEST 2: AUTH -> REVERSAL -> SECOND REVERSAL
REM ==============================
echo [TEST 2] AUTH -> REVERSAL -> SECOND REVERSAL
call :auth AUTH2_ID
call :reversal %AUTH2_ID% first_reversal
call :reversal %AUTH2_ID% second_reversal
echo.

REM ==============================
REM  TEST 3: REVERSAL FAKE ID
REM ==============================
echo [TEST 3] REVERSAL FAKE ID
set FAKE_ID=11111111-2222-3333-4444-555555555555
call :reversal %FAKE_ID% fake_reversal
echo.

REM ==============================
REM  TEST 4: AUTH -> CAPTURE -> PARTIAL REFUNDS
REM  5000 capture => refund 3000 + 2000
REM ==============================
echo [TEST 4] AUTH -> CAPTURE -> PARTIAL REFUND x2
call :auth AUTH3_ID
call :capture %AUTH3_ID% 5000 CAPTURE3_ID
call :refund_partial %CAPTURE3_ID% 3000 partial_refund_1
call :refund_partial %CAPTURE3_ID% 2000 partial_refund_2
echo.

echo ==============================================
echo   ТЕСТЫ ЗАВЕРШЕНЫ
echo ==============================================
goto :eof

REM =========================================================
REM  SUBROUTINES
REM =========================================================

:auth
REM :auth OUT_VAR_NAME
set OUTVAR=%1
set "OP_ID="
echo.
echo --- AUTH (terminal-auth) ---
for /f "tokens=2 delims=:," %%A in ('curl -s -X POST "%BASE_URL%/api/v1/processing/terminal-auth" -H "Content-Type: application/json" -d "@%REQ_FILE%" ^| findstr "operation_id"') do (
    set "OP_ID=%%~A"
)
if "!OP_ID!"=="" (
  echo [ERROR] AUTH не вернул operation_id.
  exit /b 1
)
echo AUTH operation_id=!OP_ID!
set %OUTVAR%=!OP_ID!
echo Сохранено в %OUTVAR% = !OP_ID!
goto :eof


:capture
REM :capture AUTH_ID AMOUNT OUT_VAR_NAME
set AUTH_ID=%1
set AMOUNT=%2
set OUTVAR=%3
set "CAP_ID="
echo.
echo --- CAPTURE (AUTH_ID=%AUTH_ID%, amount=%AMOUNT%) ---
for /f "tokens=2 delims=:," %%A in ('curl -s -X POST "%BASE_URL%/api/v1/transactions/%AUTH_ID%/capture" -H "Content-Type: application/json" -d "{\"amount\": %AMOUNT%}" ^| findstr "\"operation_id\""') do (
    set "CAP_ID=%%~A"
)
if "!CAP_ID!"=="" (
  echo [ERROR] CAPTURE не вернул operation_id.
  exit /b 1
)
echo CAPTURE operation_id=!CAP_ID!
set %OUTVAR%=!CAP_ID!
echo Сохранено в %OUTVAR% = !CAP_ID!
goto :eof


:reversal
REM :reversal OP_ID REASON
set OP_ID=%1
set REASON=%2
echo.
echo --- REVERSAL (op_id=%OP_ID%, reason=%REASON%) ---
curl -s -X POST "%BASE_URL%/api/v1/transactions/%OP_ID%/reversal" -H "Content-Type: application/json" -d "{\"reason\": \"%REASON%\"}"
echo.
goto :eof


:refund_full
REM :refund_full CAPTURE_ID REASON (FULL REFUND без суммы)
set CAP_ID=%1
set REASON=%2
echo.
echo --- FULL REFUND (capture_id=%CAP_ID%, reason=%REASON%) ---
curl -s -X POST "%BASE_URL%/api/v1/transactions/%CAP_ID%/refund" -H "Content-Type: application/json" -d "{\"reason\": \"%REASON%\"}"
echo.
goto :eof


:refund_partial
REM :refund_partial CAPTURE_ID AMOUNT REASON
set CAP_ID=%1
set AMOUNT=%2
set REASON=%3
echo.
echo --- PARTIAL REFUND (capture_id=%CAP_ID%, amount=%AMOUNT%, reason=%REASON%) ---
curl -s -X POST "%BASE_URL%/api/v1/transactions/%CAP_ID%/refund" -H "Content-Type: application/json" -d "{\"amount\": %AMOUNT%, \"reason\": \"%REASON%\"}"
echo.
goto :eof
