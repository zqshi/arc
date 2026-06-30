"""z21 schema drift consolidation migration 端到端验证 (M1)。

建临时 DB → upgrade head → alembic check 干净 → downgrade z20 → upgrade head → 再 check 干净。
固化 M1 修复 (migration 链终态对齐模型), 防止未来 model/migration 漂移再积累。

根因背景: v6.19 续7补3 审计曾把 review_feedbacks 误判为死表 (实为 models/__init__.py
漏 import 导致未注册 metadata)。本测试确保 migration 链 upgrade head 后 schema 严格
等于模型 metadata — 任何未来 model 改动未同步 migration 会被此测试捕获。
"""
from __future__ import annotations

import os
import subprocess
import uuid

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ALEMBIC = os.path.join(BACKEND_DIR, ".venv", "bin", "alembic")


def _run(*args: str, db_url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "ARC_DATABASE_URL": db_url}
    return subprocess.run(
        [ALEMBIC, *args], cwd=BACKEND_DIR, env=env, capture_output=True, text=True
    )


@pytest.fixture(scope="module")
def temp_db():
    """建临时 DB, 测完强制删除 (asyncpg 不支持 createdb, 用 createdb 命令)。"""
    db_name = f"arc_migrate_test_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["createdb", "-U", "zqs", db_name], check=True, capture_output=True
    )
    yield f"postgresql+asyncpg://zqs@localhost:5432/{db_name}"
    subprocess.run(
        ["dropdb", "-U", "zqs", "--if-exists", db_name], capture_output=True
    )


def test_migration_head_schema_matches_model(temp_db: str) -> None:
    """upgrade head 后 alembic check 必须干净 (migration 链终态 == 模型 metadata)。"""
    r = _run("upgrade", "head", db_url=temp_db)
    assert r.returncode == 0, f"upgrade head failed:\n{r.stderr}"

    r = _run("check", db_url=temp_db)
    assert r.returncode == 0, f"alembic check not clean after upgrade:\n{r.stdout}\n{r.stderr}"
    assert "No new upgrade operations detected" in r.stdout + r.stderr


def test_migration_z21_reversible(temp_db: str) -> None:
    """z21 downgrade/upgrade 双向可逆, 且双向后 check 仍干净。"""
    # 起点已在 head (前一个测试 upgrade 过); 确保在 head
    _run("upgrade", "head", db_url=temp_db)

    r = _run("downgrade", "z20_ios_harmony_creds", db_url=temp_db)
    assert r.returncode == 0, f"downgrade z21 failed:\n{r.stderr}"

    r = _run("upgrade", "head", db_url=temp_db)
    assert r.returncode == 0, f"re-upgrade z21 failed:\n{r.stderr}"

    r = _run("check", db_url=temp_db)
    assert r.returncode == 0, f"alembic check not clean after roundtrip:\n{r.stdout}\n{r.stderr}"
    assert "No new upgrade operations detected" in r.stdout + r.stderr


def test_review_feedbacks_table_alive(temp_db: str) -> None:
    """review_feedbacks 是活跃表 (非死表), upgrade head 后必须存在。

    防止误判死表回潮 (v6.19 续7补3 误判教训)。
    """
    _run("upgrade", "head", db_url=temp_db)
    r = subprocess.run(
        ["psql", "-U", "zqs", "-d", temp_db.split("/")[-1], "-tAc",
         "SELECT to_regclass('review_feedbacks');"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"psql failed: {r.stderr}"
    assert r.stdout.strip() == "review_feedbacks", \
        f"review_feedbacks 表缺失: {r.stdout!r}"
