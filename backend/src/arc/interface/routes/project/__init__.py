from fastapi import APIRouter

from arc.interface.routes.project.core import router as core_router
from arc.interface.routes.project.experiences import router as experiences_router
from arc.interface.routes.project.members import router as members_router
from arc.interface.routes.project.operations import router as operations_router
from arc.interface.routes.project.planning import router as planning_router
from arc.interface.routes.project.versions import router as versions_router

router = APIRouter()

# Merge sub-router routes directly to avoid FastAPI validation error when
# including routers with empty-path routes ("") under another router with
# no prefix.
for _sub in (
    core_router,
    operations_router,
    members_router,
    versions_router,
    experiences_router,
    planning_router,
):
    for route in _sub.routes:
        router.routes.append(route)
