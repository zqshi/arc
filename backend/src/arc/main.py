import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from arc.config import settings
from arc.domain.errors import AppError
from arc.domain.pipeline.entity import InvalidPhaseTransitionError
from arc.domain.todo.entity import InvalidStatusTransitionError
from arc.interface.middleware.request_id import RequestIdFilter

_BASE_ATTRS: frozenset[str] | None = None


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        global _BASE_ATTRS
        if _BASE_ATTRS is None:
            _BASE_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
                "message",
                "msg",
                "args",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            }

        ts = self.formatTime(record)
        rid = getattr(record, "request_id", "")
        rid_tag = f" [{rid}]" if rid else ""
        base = f"{ts} {record.levelname:<8} {record.name}{rid_tag} — {record.getMessage()}"
        extras = {k: v for k, v in record.__dict__.items() if k not in _BASE_ATTRS}
        if extras:
            pairs = " ".join(f"{k}={v}" for k, v in extras.items())
            base += f" | {pairs}"
        return base


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(StructuredFormatter())
handler.addFilter(RequestIdFilter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[handler],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arc backend starting (debug=%s)", settings.debug)
    if not settings.debug and not settings.jwt_secret:
        raise RuntimeError("ARC_JWT_SECRET must be set in production mode")
    await _cleanup_orphan_agent_sessions()
    from arc.seeds import ensure_seed_users

    await ensure_seed_users()

    decay_task = asyncio.create_task(_experience_decay_loop())
    yield
    decay_task.cancel()
    from arc.application.ai.adapter_pool import adapter_pool

    await adapter_pool.shutdown()
    logger.info("Arc backend shut down")


async def _cleanup_orphan_agent_sessions():
    try:
        from sqlalchemy import update

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.models.agent import AgentSessionModel as AgentModel

        async with async_session_factory() as db:
            result = await db.execute(
                update(AgentModel)
                .where(AgentModel.status.in_(["pending", "running", "paused"]))
                .values(status="error", error_reason="服务重启，会话已中断")
            )
            if result.rowcount > 0:
                logger.warning("Cleaned up %d orphan agent sessions", result.rowcount)
            await db.commit()
    except Exception as exc:
        logger.warning("Orphan session cleanup failed: %s", exc)


_DECAY_INTERVAL = 24 * 3600


async def _experience_decay_loop():
    await asyncio.sleep(60)
    while True:
        try:
            from arc.application.experience.service import ExperienceService
            from arc.infrastructure.database import async_session_factory

            async with async_session_factory() as db:
                svc = ExperienceService(db)
                count = await svc.decay_batch()
                if count > 0:
                    logger.info("Experience decay: updated %d records", count)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Experience decay loop error: %s", exc)
        await asyncio.sleep(_DECAY_INTERVAL)


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)

_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:3001",
]

_cors_origins = list(settings.cors_origins)
if settings.debug:
    for o in _DEV_ORIGINS:
        if o not in _cors_origins:
            _cors_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

from arc.interface.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from arc.interface.middleware.request_id import RequestIdMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


@app.exception_handler(InvalidStatusTransitionError)
async def handle_invalid_transition(request: Request, exc: InvalidStatusTransitionError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": "INVALID_STATUS_TRANSITION"},
    )


@app.exception_handler(InvalidPhaseTransitionError)
async def handle_invalid_phase_transition(request: Request, exc: InvalidPhaseTransitionError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": "INVALID_PHASE_TRANSITION"},
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": f"HTTP_{exc.status_code}"},
    )


@app.exception_handler(Exception)
async def handle_unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务内部错误", "error_code": "INTERNAL_ERROR"},
    )


@app.get("/health")
async def health():
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
    from arc.interface.routes.agent import router as agent_router
    from arc.interface.routes.auth import router as auth_router
    from arc.interface.routes.billing import router as billing_router
    from arc.interface.routes.conversation import router as conversation_router
    from arc.interface.routes.experience import router as experience_router
    from arc.interface.routes.filesystem import router as filesystem_router
    from arc.interface.routes.organization import router as org_router
    from arc.interface.routes.pipeline import router as pipeline_router
    from arc.interface.routes.project import router as project_router
    from arc.interface.routes.settings import router as settings_router
    from arc.interface.routes.todo import router as todo_router
    from arc.interface.routes.webhook import router as webhook_router
    from arc.interface.ws.chat import router as ws_router

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(org_router, prefix="/api/orgs", tags=["organizations"])
    app.include_router(billing_router, prefix="/api/billing", tags=["billing"])
    app.include_router(project_router, prefix="/api/projects", tags=["projects"])
    app.include_router(todo_router, prefix="/api/todos", tags=["todos"])
    app.include_router(pipeline_router, prefix="/api/todos", tags=["pipeline"])
    app.include_router(agent_router, prefix="/api/todos", tags=["agent"])
    app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
    app.include_router(experience_router, prefix="/api/experiences", tags=["experiences"])
    app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
    app.include_router(filesystem_router, prefix="/api/filesystem", tags=["filesystem"])
    app.include_router(webhook_router, prefix="/api/webhooks", tags=["webhooks"])
    app.include_router(ws_router, prefix="/ws", tags=["websocket"])

    from arc.config import settings

    if not settings.storage_endpoint:
        from pathlib import Path

        from fastapi.staticfiles import StaticFiles

        static_dir = Path(__file__).resolve().parent.parent / "static" / "previews"
        static_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/static/previews",
            StaticFiles(directory=str(static_dir), follow_symlink=True),
            name="previews",
        )


register_routes()
