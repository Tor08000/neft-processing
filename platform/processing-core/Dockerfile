# platform/processing-core/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# кладём shared/python как отдельный модуль
COPY shared/python /opt/python
ENV PYTHONPATH=/opt/python:/app

# подключаем sitecustomize.py, чтобы он подхватывался автоматически
COPY sitecustomize.py /app/sitecustomize.py

# ставим зависимости core-api
COPY platform/processing-core/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# сам код core-api
COPY platform/processing-core /app

# entrypoint
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
