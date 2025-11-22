@echo off
REM === Сохранить структуру папки в текстовый файл ===
REM Использование: tree_to_file.cmd "C:\путь\к\папке" "результат.txt"

setlocal
set TARGET=%~1
set OUTPUT=%~2

if "%TARGET%"=="" set TARGET=.
if "%OUTPUT%"=="" set OUTPUT=structure.txt

echo [*] Building folder tree for %TARGET%
tree "%TARGET%" /F /A > "%OUTPUT%"

echo [*] Structure saved to %OUTPUT%
endlocal
pause