# platform/integration-hub/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY platform/integration-hub/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared/python /opt/python
ENV PYTHONPATH=/app:/opt/python

# sitecustomize
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/integration-hub /app

EXPOSE 8000

CMD ["uvicorn", "neft_integration_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
