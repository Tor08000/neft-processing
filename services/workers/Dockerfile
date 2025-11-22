FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 1. Ставим зависимости воркеров
COPY services/workers/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 2. Кладём общую питон-библиотеку и добавляем её в PYTHONPATH
#    ВАЖНО: копируем всю shared/python, чтобы внутри был /opt/python/neft_shared
COPY shared/python /opt/python
# Дублируем пакет в /app, чтобы он был на стандартном sys.path, даже
# если переменные окружения не попадут в контейнер.
COPY shared/python/neft_shared /app/neft_shared
ENV PYTHONPATH="/opt/python:/app"

# 3. Копируем код воркеров
COPY services/workers /app/services/workers

# 4. Чиним переводы строк и права у entrypoint.sh
RUN sed -i 's/\r$//' /app/services/workers/entrypoint.sh \
    && chmod +x /app/services/workers/entrypoint.sh

# 5. Общая точка входа (он сам решает, worker или beat по переменным)
ENTRYPOINT ["/app/services/workers/entrypoint.sh"]
