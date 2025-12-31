FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Кладём общий код
COPY shared/python /opt/python

# Очень важно: чтобы neft_shared был виден
ENV PYTHONPATH="/opt/python:/app"

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
