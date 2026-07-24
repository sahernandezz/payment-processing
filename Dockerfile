FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY libs/payment-db-models /app/libs/payment-db-models
COPY services/api /app/services/api
COPY services/reconciliation /app/services/reconciliation
COPY scripts /app/scripts

RUN pip install ./libs/payment-db-models \
    && pip install ./services/api \
    && pip install ./services/reconciliation

EXPOSE 8000 9808

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
