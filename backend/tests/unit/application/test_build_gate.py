"""构建门禁单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc.application.execution.build_gate import (
    BuildGateError,
    BuildGateResult,
    check_build_ready,
)


class TestCheckBuildReady:
    def test_success_with_non_empty_dist(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("<html/>")
        result = check_build_ready(build_status="success", dist_dir=tmp_path)
        assert result.ok is True

    def test_fails_when_build_status_not_success(self, tmp_path: Path) -> None:
        result = check_build_ready(build_status="failed", dist_dir=tmp_path)
        assert result.ok is False
        assert "success" in result.reason

    def test_fails_when_build_status_none(self, tmp_path: Path) -> None:
        result = check_build_ready(build_status=None, dist_dir=tmp_path)
        assert result.ok is False

    def test_fails_when_dist_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        result = check_build_ready(build_status="success", dist_dir=missing)
        assert result.ok is False
        assert "不存在" in result.reason

    def test_fails_when_dist_empty(self, tmp_path: Path) -> None:
        result = check_build_ready(build_status="success", dist_dir=tmp_path)
        assert result.ok is False
        assert "为空" in result.reason

    def test_allow_empty_when_disabled(self, tmp_path: Path) -> None:
        result = check_build_ready(
            build_status="success", dist_dir=tmp_path, require_non_empty=False,
        )
        assert result.ok is True


class TestEnsureOk:
    def test_ensure_ok_passes_when_ready(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("x")
        check_build_ready(build_status="success", dist_dir=tmp_path).ensure_ok()

    def test_ensure_ok_raises_when_not_ready(self, tmp_path: Path) -> None:
        result = BuildGateResult(ok=False, reason="bad")
        with pytest.raises(BuildGateError, match="bad"):
            result.ensure_ok()
