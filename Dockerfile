# Production API image — build from repo root:
#   docker build -t recoup-api .
# Includes eval_fixtures + sla_catalog for promote/replay paths.

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY backend/pyproject.toml ./
COPY backend/src ./src
COPY eval_fixtures /app/eval_fixtures
COPY sla_catalog /app/sla_catalog

RUN pip install --upgrade pip && pip install .

ENV PORT=8080
EXPOSE 8080

# App Runner sets PORT; default 8080 (see RecoupAppStack imageConfiguration.port).
CMD ["sh", "-c", "exec uvicorn recoup.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
