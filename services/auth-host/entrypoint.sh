#!/usr/bin/env bash
set -e

# На всякий случай ещё раз прописываем PYTHONPATH
export PYTHONPATH="/opt/python:${PYTHONPATH}"

echo "[entrypoint] auth-host starting"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
