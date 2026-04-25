FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY platform/auth-host/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared/python /opt/python
ENV PYTHONPATH="/app:/opt/python"

# sitecustomize is copied into /app so Python imports it automatically.
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/auth-host /app

COPY platform/auth-host/entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["./entrypoint.sh"]
