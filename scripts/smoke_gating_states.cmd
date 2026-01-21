@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Smoke: UX gating states (client/partner/admin)
REM This script is intentionally lightweight and should be expanded per environment.

echo [INFO] Smoke gating states placeholder.
echo [INFO] Validate:
echo   - Client: org not active -> activation screen
echo   - Client: overdue -> payment required screen
echo   - Client: plan missing -> paywall screen
echo   - Partner: legal not verified -> checklist screen
echo   - Partner: payout blocked -> blockers screen
echo   - Admin: forbidden role -> forbidden page

exit /b 0
