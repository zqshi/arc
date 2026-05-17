import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from arc.config import settings
from arc.domain.pipeline.entity import InvalidPhaseTransition
from arc.domain.todo.entity import InvalidStatusTransition


class StructuredFormatter(logging.Formatter):
    """Compact structured log format for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record)
        base = f"{ts} {record.levelname:<8} {record.name} — {record.getMessage()}"
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__ and k not in (
                "message", "msg", "args", "exc_info", "exc_text", "stack_info",
                "taskName",
            )
        }
        if extras:
            pairs = " ".join(f"{k}={v}" for k, v in extras.items())
            base += f" | {pairs}"
        return base


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(StructuredFormatter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[handler],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arc backend starting (debug=%s)", settings.debug)
    yield
    from arc.application.ai.adapter_pool import adapter_pool
    await adapter_pool.shutdown()
    logger.info("Arc backend shut down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(InvalidStatusTransition)
async def handle_invalid_transition(request: Request, exc: InvalidStatusTransition):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidPhaseTransition)
async def handle_invalid_phase_transition(request: Request, exc: InvalidPhaseTransition):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
async def health():
    """Deep health check: DB connectivity and LLM reachability."""
    from sqlalchemy import text

    from arc.infrastructure.database import async_session_factory

    checks: dict = {"status": "ok"}

    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        checks["status"] = "degraded"

    return checks


def register_routes():
    from arc.interface.routes.conversation import router as conversation_router
    from arc.interface.routes.experience import router as experience_router
    from arc.interface.routes.pipeline import router as pipeline_router
    from arc.interface.routes.todo import router as todo_router
    from arc.interface.ws.chat import router as ws_router

    app.include_router(todo_router, prefix="/api/todos", tags=["todos"])
    app.include_router(pipeline_router, prefix="/api/todos", tags=["pipeline"])
    app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
    app.include_router(experience_router, prefix="/api/experiences", tags=["experiences"])
    app.include_router(ws_router, prefix="/ws", tags=["websocket"])


register_routes()
