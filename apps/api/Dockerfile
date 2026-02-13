FROM python:3.11-slim

WORKDIR /app
COPY app.py .

RUN pip install fastapi uvicorn prometheus_client \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
