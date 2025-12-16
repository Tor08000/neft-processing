FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Базовые зависимости для сборки (если что-то компилируется)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Кладём общий код
COPY shared/python /opt/python

# Очень важно: чтобы neft_shared был виден
ENV PYTHONPATH="/opt/python:${PYTHONPATH}"

# подключаем sitecustomize.py, чтобы он подхватывался автоматически
COPY sitecustomize.py /app/sitecustomize.py

# Ставим зависимости auth-host
COPY platform/auth-host/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Сам сервис
COPY platform/auth-host /app

# Наш entrypoint
COPY platform/auth-host/entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["./entrypoint.sh"]
