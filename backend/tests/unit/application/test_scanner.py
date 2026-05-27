from __future__ import annotations

import os
import tempfile

from arc.application.project.scanner import CodebaseScanner, IGNORE_DIRS, KEY_FILES


class TestCodebaseScannerTree:
    def test_scan_returns_tree_and_files(self, tmp_path) -> None:
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.scan()

        assert data["path"] == str(tmp_path)
        assert "src/" in data["tree"]
        assert "main.py" in data["tree"]
        assert "README.md" in data["files"]

    def test_ignores_directories(self, tmp_path) -> None:
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.json").write_text("{}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")

        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.scan()
        assert "node_modules" not in data["tree"]

    def test_invalid_path_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="不存在"):
            CodebaseScanner("/nonexistent/path/12345")


class TestCodebaseScannerKeyFiles:
    def test_reads_package_json(self, tmp_path) -> None:
        (tmp_path / "package.json").write_text('{"name": "test"}')
        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.scan()
        assert "package.json" in data["files"]
        assert '"name"' in data["files"]["package.json"]

    def test_truncates_large_files(self, tmp_path) -> None:
        large_content = "x" * 10000
        (tmp_path / "README.md").write_text(large_content)
        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.scan()
        assert "已截断" in data["files"]["README.md"]
        assert len(data["files"]["README.md"]) < 10000


class TestCodebaseScannerPrompt:
    def test_build_prompt(self, tmp_path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.pytest]')
        scanner = CodebaseScanner(str(tmp_path))
        prompt = scanner.build_prompt()
        assert "代码库分析专家" in prompt
        assert "pyproject.toml" in prompt
