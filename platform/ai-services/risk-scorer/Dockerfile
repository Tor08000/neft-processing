FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY platform/ai-services/risk-scorer/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

COPY shared/python /opt/python
ENV PYTHONPATH="/app:/opt/python"

# sitecustomize is copied into /app so Python imports it automatically.
COPY sitecustomize.py /app/sitecustomize.py

COPY platform/ai-services/risk-scorer /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
