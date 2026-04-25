FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Keep dependency layers independent from shared runtime code changes.
COPY platform/billing-clearing/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared/python /opt/python
ENV PYTHONPATH="/app/services/workers:/app:/opt/python"

# sitecustomize is copied into /app so Python imports it automatically.
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/billing-clearing /app/services/workers

RUN sed -i 's/\r$//' /app/services/workers/entrypoint.sh \
    && chmod +x /app/services/workers/entrypoint.sh

WORKDIR /app/services/workers

ENTRYPOINT ["/app/services/workers/entrypoint.sh"]
