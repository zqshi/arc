"""Filesystem browsing API for local workspace selection."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class BrowseResponse(BaseModel):
    current: str
    parent: str | None
    dirs: list[str]


class MkdirRequest(BaseModel):
    path: str


class MkdirResponse(BaseModel):
    path: str


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(path: str = "~"):
    resolved = Path(os.path.expanduser(path)).resolve()
    if not resolved.exists():
        raise HTTPException(404, f"路径不存在: {resolved}")
    if not resolved.is_dir():
        raise HTTPException(400, f"不是目录: {resolved}")

    try:
        dirs = sorted(
            [
                entry.name
                for entry in resolved.iterdir()
                if entry.is_dir() and not entry.name.startswith(".")
            ]
        )
    except PermissionError:
        raise HTTPException(403, f"无权限访问: {resolved}")

    parent = str(resolved.parent) if resolved.parent != resolved else None
    return BrowseResponse(current=str(resolved), parent=parent, dirs=dirs)


@router.post("/mkdir", response_model=MkdirResponse)
async def create_directory(body: MkdirRequest):
    target = Path(os.path.expanduser(body.path)).resolve()
    if target.exists():
        raise HTTPException(409, f"目录已存在: {target}")
    try:
        target.mkdir(parents=True, exist_ok=False)
    except PermissionError:
        raise HTTPException(403, f"无权限创建: {target}")
    except OSError as e:
        raise HTTPException(400, f"创建失败: {e}")
    return MkdirResponse(path=str(target))
