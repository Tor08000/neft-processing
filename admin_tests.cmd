@echo off
setlocal ENABLEDELAYEDEXPANSION

set "BASE_URL=http://localhost"

echo ==== ADMIN TESTS ====

REM --- 1. Проверяем, что TOKEN задан ---
if "%TOKEN%"=="" (
  echo [ERROR] Переменная окружения TOKEN пуста.
  echo.
  echo Сначала залогинься и установи токен вручную:
  echo   curl -s -X POST "http://localhost:8002/api/v1/auth/login" ^
       -H "Content-Type: application/json" ^
       -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}"
  echo.
  echo Потом в этом же окне CMD:
  echo   set TOKEN=СКОПИРОВАННЫЙ_ACCESS_TOKEN
  echo   admin_tests.cmd
  echo.
  pause
  exit /b 1
)

echo [OK] TOKEN найден.
echo.

REM --- 2. Последние 5 операций ---
echo ==== ADMIN OPERATIONS (last 5) ====
curl -s -H "Authorization: Bearer %TOKEN%" ^
  "%BASE_URL%/api/v1/admin/operations?limit=5&offset=0"
echo.
echo.

REM --- 3. Последние 5 транзакций ---
echo ==== ADMIN TRANSACTIONS (last 5) ====
curl -s -H "Authorization: Bearer %TOKEN%" ^
  "%BASE_URL%/api/v1/admin/transactions?limit=5&offset=0"
echo.
echo.

REM --- 4. Все REFUND операции ---
echo ==== REFUND OPERATIONS ====
curl -s -H "Authorization: Bearer %TOKEN%" ^
  "%BASE_URL%/api/v1/admin/operations?operation_type=REFUND&limit=10"
echo.
echo.

REM --- 5. Транзакции конкретного клиента ---
echo ==== CLIENT CLIENT-123 TRANSACTIONS ====
curl -s -H "Authorization: Bearer %TOKEN%" ^
  "%BASE_URL%/api/v1/admin/transactions?client_id=CLIENT-123&limit=10"
echo.
echo.

REM --- 6. Операции, отсортированные по сумме (DESC) ---
echo ==== OPERATIONS ORDERED BY AMOUNT DESC ====
curl -s -H "Authorization: Bearer %TOKEN%" ^
  "%BASE_URL%/api/v1/admin/operations?order_by=amount_desc&limit=10"
echo.
echo.

echo ==== DONE ====
pause

endlocal
