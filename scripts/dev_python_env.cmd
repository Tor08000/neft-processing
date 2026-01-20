@echo off
setlocal EnableExtensions

set "ROOT=%CD%"

pip install -e "%ROOT%\shared\python"

set "PYTHONPATH=%ROOT%\platform\processing-core;%ROOT%"
python -c "import neft_shared; import app.main"
