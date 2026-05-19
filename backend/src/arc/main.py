import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from arc.config import settings
from arc.domain.errors import AppError
from arc.domain.pipeline.entity import InvalidPhaseTransition
from arc.domain.todo.entity import InvalidStatusTransition

_BASE_ATTRS: frozenset[str] | None = None


class StructuredFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        global _BASE_ATTRS
        if _BASE_ATTRS is None:
            _BASE_ATTRS = frozenset(
                logging.LogRecord("", 0, "", 0, "", (), None).__dict__
            ) | {"message", "msg", "args", "exc_info", "exc_text", "stack_info", "taskName"}

        ts = self.formatTime(record)
        base = f"{ts} {record.levelname:<8} {record.name} — {record.getMessage()}"
        extras = {
            k: v for k, v in record.__dict__.items() if k not in _BASE_ATTRS
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
    await _cleanup_orphan_agent_sessions()
    await _ensure_seed_users()
    yield
    from arc.application.ai.adapter_pool import adapter_pool
    await adapter_pool.shutdown()
    logger.info("Arc backend shut down")


async def _cleanup_orphan_agent_sessions():
    try:
        from sqlalchemy import update

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.models.agent import AgentSession as AgentModel

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


async def _ensure_seed_users():
    """Create default test accounts on first startup (debug only)."""
    if not settings.debug:
        return
    try:
        from arc.application.auth.password import hash_password
        from arc.domain.user.entity import User
        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository
        from arc.infrastructure.repositories.user import UserRepository

        seed_accounts = [
            {"username": "demo", "password": "demo123", "display_name": "Demo 用户"},
            {"username": "test", "password": "test123", "display_name": "测试用户"},
        ]

        async with async_session_factory() as db:
            user_repo = UserRepository(db)
            for acct in seed_accounts:
                existing = await user_repo.get_by_username(acct["username"])
                if existing:
                    continue
                user = User(
                    username=acct["username"],
                    hashed_password=hash_password(acct["password"]),
                    display_name=acct["display_name"],
                )
                await user_repo.create(user)
                logger.info("Seed user created: %s", acct["username"])
            await db.commit()

            proj_repo = ProjectRepository(db)
            for acct in seed_accounts:
                u = await user_repo.get_by_username(acct["username"])
                if not u:
                    continue
                existing = await proj_repo.list_all(user_id=u.id)
                if existing:
                    continue
                await _create_seed_data(db, u.id)
                await db.commit()
                logger.info("Seed demo data created for user: %s", acct["username"])
    except Exception as exc:
        logger.warning("Seed user creation failed: %s", exc)


async def _create_seed_data(db, user_id):
    """Populate demo user with full-chain sample data."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    from seed_data import create_seed_data
    await create_seed_data(db, user_id)


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)

_DEV_ORIGINS = [
    "http://localhost:5173", "http://localhost:5174",
    "http://localhost:5175", "http://localhost:5176",
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

app.add_middleware(RateLimitMiddleware)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


@app.exception_handler(InvalidStatusTransition)
async def handle_invalid_transition(request: Request, exc: InvalidStatusTransition):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": "INVALID_STATUS_TRANSITION"},
    )


@app.exception_handler(InvalidPhaseTransition)
async def handle_invalid_phase_transition(request: Request, exc: InvalidPhaseTransition):
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
    from arc.interface.routes.conversation import router as conversation_router
    from arc.interface.routes.experience import router as experience_router
    from arc.interface.routes.pipeline import router as pipeline_router
    from arc.interface.routes.project import router as project_router
    from arc.interface.routes.settings import router as settings_router
    from arc.interface.routes.todo import router as todo_router
    from arc.interface.ws.chat import router as ws_router

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(project_router, prefix="/api/projects", tags=["projects"])
    app.include_router(todo_router, prefix="/api/todos", tags=["todos"])
    app.include_router(pipeline_router, prefix="/api/todos", tags=["pipeline"])
    app.include_router(agent_router, prefix="/api/todos", tags=["agent"])
    app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
    app.include_router(experience_router, prefix="/api/experiences", tags=["experiences"])
    app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
    app.include_router(ws_router, prefix="/ws", tags=["websocket"])


register_routes()
