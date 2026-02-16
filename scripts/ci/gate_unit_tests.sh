#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e shared/python
python -m pip install -r platform/auth-host/requirements.txt
python -m pip install -r platform/processing-core/requirements.txt
python -m pip install -r platform/integration-hub/requirements.txt

pytest -q platform/auth-host/app/tests
pytest -q platform/processing-core/app/tests
pytest -q platform/integration-hub/neft_integration_hub/tests
