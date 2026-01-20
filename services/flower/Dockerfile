FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Flower ставится через pip, поэтому нужны pip и зависимости ОС
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Ставим зависимости Celery-приложения воркеров и Flower
COPY platform/billing-clearing/requirements.txt /tmp/worker-requirements.txt
COPY services/flower/requirements.txt /tmp/flower-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt \
    && pip install --no-cache-dir -r /tmp/flower-requirements.txt

# Кладём общую питон-библиотеку и код воркеров, чтобы Celery app был доступен
COPY shared/python /opt/python
RUN pip install -e /opt/python
ENV PYTHONPATH="/app/services/workers:/app"

# подключаем sitecustomize.py, чтобы он подхватывался автоматически
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/billing-clearing /app/services/workers

WORKDIR /app/services/workers

CMD ["python", "-m", "celery", "-A", "app.celery_app:celery_app", "flower", "--port=5555", "--address=0.0.0.0"]
