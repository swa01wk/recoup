FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn recoup.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
