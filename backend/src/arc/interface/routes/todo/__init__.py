from fastapi import APIRouter

from arc.interface.routes.todo.crud import router as crud_router
from arc.interface.routes.todo.git import router as git_router
from arc.interface.routes.todo.conversations import router as conversations_router

router = APIRouter()

for _sub in (crud_router, git_router, conversations_router):
    for route in _sub.routes:
        router.routes.append(route)
