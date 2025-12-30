FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY platform/logistics-service/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

COPY platform/logistics-service /app

EXPOSE 8000

CMD ["uvicorn", "neft_logistics_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
