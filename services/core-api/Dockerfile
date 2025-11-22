FROM python:3.11-slim

# Provide system psycopg2 wheel so the driver is always importable even if
# Python package installation is skipped or overridden in some environments.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-psycopg2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 1. Устанавливаем зависимости core-api
COPY services/core-api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 2. Кладём общую библиотеку
COPY shared/python /opt/python
# Дублируем пакет в /app, чтобы он всегда был на стандартном sys.path,
# даже если переменные окружения перетрут PYTHONPATH.
COPY shared/python/neft_shared /app/neft_shared
ENV PYTHONPATH="/opt/python:/app"

# 3. Копируем ВЕСЬ core-api, а не только app/
COPY services/core-api /app

# 4. Чиним CRLF и делаем entrypoint исполняемым
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
