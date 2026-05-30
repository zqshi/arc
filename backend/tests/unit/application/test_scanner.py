from __future__ import annotations

import os

from arc.application.project.scanner import CodebaseScanner, IGNORE_DIRS


class TestCodebaseScannerTree:
    def test_full_scan_returns_tree_and_files(self, tmp_path) -> None:
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.full_scan()

        assert data["path"] == str(tmp_path)
        assert "src/" in data["tree"]
        assert "main.py" in data["tree"]
        # source_files contains readable content keyed by relative path
        assert any("README" in k for k in data["source_files"])

    def test_ignores_directories(self, tmp_path) -> None:
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.json").write_text("{}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")

        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.full_scan()
        assert "node_modules" not in data["tree"]

    def test_invalid_path_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="不存在"):
            CodebaseScanner("/nonexistent/path/12345")

    def test_returns_stats(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.full_scan()
        assert "stats" in data
        assert data["stats"]["total_files"] >= 1

    def test_returns_scale(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.full_scan()
        assert data["scale"] is not None


class TestCodebaseScannerKeyFiles:
    def test_reads_package_json(self, tmp_path) -> None:
        (tmp_path / "package.json").write_text('{"name": "test"}')
        scanner = CodebaseScanner(str(tmp_path))
        data = scanner.full_scan()
        pkg_content = [v for k, v in data["source_files"].items() if "package.json" in k]
        assert len(pkg_content) > 0
        assert '"name"' in pkg_content[0]
