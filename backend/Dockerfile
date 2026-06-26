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

# 本地存储模式预览目录(命名卷挂载, 首次复制继承权限, arc 用户可写)
RUN mkdir -p /app/data/static && chown -R arc:arc /app/data

USER arc

EXPOSE 8000
# v6.7: 多 worker 需配 ARC_REDIS_URL (跨进程事件总线), 否则单 worker。
# 无 redis 时设 ARC_WORKERS=1 退回进程内 InMemory 模式。
ENV ARC_WORKERS=2
CMD ["sh", "-c", "alembic upgrade head && uvicorn arc.main:app --host 0.0.0.0 --port 8000 --workers ${ARC_WORKERS}"]
