# services/core-api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# нужно для psycopg[binary] и curl для healthcheck'а
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# кладём shared/python как отдельный модуль
COPY shared/python /opt/python
ENV PYTHONPATH=/opt/python:/app

# ставим зависимости core-api
COPY services/core-api/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# сам код core-api
COPY services/core-api /app

# entrypoint
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
