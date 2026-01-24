# platform/processing-core/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# кладём shared/python как отдельный модуль
COPY shared/python /opt/python
RUN pip install -e /opt/python
ENV PYTHONPATH=/app

# подключаем sitecustomize.py, чтобы он подхватывался автоматически
COPY sitecustomize.py /app/sitecustomize.py

# ставим зависимости core-api
COPY platform/processing-core/requirements.txt /tmp/requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# сам код core-api
COPY platform/processing-core /app

# dev seed scripts
COPY scripts /app/scripts

# docs (contracts event schema registry)
COPY docs /app/docs

# entrypoint
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
