FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -r -s /sbin/nologin arc

COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY alembic/ alembic/

USER arc

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn arc.main:app --host 0.0.0.0 --port 8000"]
