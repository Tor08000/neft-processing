# platform/processing-core/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Keep dependency layers independent from shared runtime code changes.
COPY platform/processing-core/requirements.txt /tmp/requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared/python /opt/python
ENV PYTHONPATH=/app:/opt/python

# sitecustomize is copied into /app so Python imports it automatically.
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/processing-core /app

# dev seed scripts
COPY scripts /app/scripts

# docs (contracts event schema registry)
COPY docs /app/docs

# gateway route topology is part of the processing-core regression surface.
COPY gateway /app/gateway

# entrypoint
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
