FROM python:3.12-slim AS base

WORKDIR /app

RUN adduser --disabled-password --no-create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY capi-proxy.py .

USER appuser

EXPOSE 8787

CMD ["uvicorn", "capi-proxy:app", "--host", "0.0.0.0", "--port", "8787", "--workers", "2", "--log-level", "warning"]
