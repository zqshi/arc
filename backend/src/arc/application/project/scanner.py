"""Codebase scanner — deep project understanding via adaptive analysis.

Design philosophy:
  - No hardcoded context limits. The scanner adapts to project scale.
  - Small projects: read everything, single-pass analysis.
  - Medium projects: intelligent sampling per module, one synthesis pass.
  - Large projects: per-module deep dives + synthesis.
  - Goal: AI finishes when it has truly understood the project, not when
    a budget is hit.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Directories to always skip (build artifacts, caches, deps)
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".tox", "coverage", ".cache",
    "vendor", "Pods", ".gradle", "out", ".egg-info", "htmlcov",
    ".ruff_cache", ".turbo", ".parcel-cache", ".svelte-kit",
}

SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".vue", ".svelte",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".br",
    ".wasm", ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".db", ".sqlite", ".sqlite3",
}

CONFIG_FILES = [
    "README.md", "README.rst", "README",
    "package.json", "pyproject.toml", "requirements.txt",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
    "Makefile", "CMakeLists.txt",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    ".env.example", "tsconfig.json", "alembic.ini", "CLAUDE.md",
]

# Files that typically define architecture (entry points, routing, models)
ARCHITECTURE_FILE_PATTERNS = {
    "main.py", "app.py", "server.py", "manage.py",
    "index.ts", "index.tsx", "main.ts", "main.tsx", "app.ts", "app.tsx",
    "index.js", "main.js", "app.js", "main.go",
    "entity.py", "entities.py", "models.py", "model.py",
    "schema.py", "schemas.py", "value_objects.py", "aggregates.py",
    "routes.py", "router.py", "urls.py", "views.py", "endpoints.py",
    "service.py", "services.py", "use_cases.py",
    "types.ts", "types.d.ts", "api.ts",
    "errors.py", "exceptions.py", "config.py", "settings.py",
}


# ---------------------------------------------------------------------------
# Project scale classification
# ---------------------------------------------------------------------------


class ProjectScale:
    """Classifies project scale to decide analysis strategy."""

    SMALL = "small"      # < 30 source files
    MEDIUM = "medium"    # 30 - 300 source files
    LARGE = "large"      # > 300 source files

    def __init__(self, source_file_count: int, total_loc: int):
        self.file_count = source_file_count
        self.total_loc = total_loc
        if source_file_count < 30:
            self.category = self.SMALL
        elif source_file_count <= 300:
            self.category = self.MEDIUM
        else:
            self.category = self.LARGE

    @property
    def read_all(self) -> bool:
        return self.category == self.SMALL

    @property
    def max_file_read_chars(self) -> int:
        if self.category == self.SMALL:
            return 20_000
        elif self.category == self.MEDIUM:
            return 6_000
        return 4_000

    @property
    def max_tokens(self) -> int:
        if self.category == self.SMALL:
            return 6000
        elif self.category == self.MEDIUM:
            return 8192
        return 10000

    def __repr__(self) -> str:
        return f"ProjectScale({self.category}: {self.file_count} files, {self.total_loc} LOC)"


# ---------------------------------------------------------------------------
# CodebaseScanner
# ---------------------------------------------------------------------------


class CodebaseScanner:
    def __init__(self, path: str):
        self.root = Path(os.path.expanduser(path)).resolve()
        if not self.root.is_dir():
            raise ValueError(f"路径不存在或不是目录: {self.root}")

    def full_scan(self) -> dict:
        """Complete scan: tree + stats + file content (scale-adaptive)."""
        tree_lines, file_index, stats = self._walk_full()
        scale = ProjectScale(stats["total_source_files"], stats["total_loc"])
        files_to_read = self._select_files(file_index, scale)
        file_contents = self._read_files(files_to_read, scale)
        config_contents = self._read_config_files()
        return {
            "path": str(self.root),
            "tree": "\n".join(tree_lines),
            "stats": stats,
            "scale": scale,
            "config_files": config_contents,
            "source_files": file_contents,
            "file_index": file_index,
        }

    # -- Phase 1: Full walk --------------------------------------------------

    def _walk_full(self) -> tuple[list[str], dict[str, dict], dict]:
        tree_lines: list[str] = []
        file_index: dict[str, dict] = {}
        ext_counter: Counter = Counter()
        dir_loc: dict[str, int] = defaultdict(int)
        dir_files: dict[str, int] = defaultdict(int)

        self._walk_recursive(
            self.root, "", tree_lines, 0,
            file_index, ext_counter, dir_loc, dir_files,
        )

        top_dirs = sorted(dir_loc.items(), key=lambda x: -x[1])[:30]
        stats = {
            "total_source_files": sum(dir_files.values()),
            "total_loc": sum(dir_loc.values()),
            "extensions": ext_counter.most_common(20),
            "top_directories": top_dirs,
            "dir_file_counts": dict(dir_files),
        }
        return tree_lines, file_index, stats

    def _walk_recursive(
        self, directory: Path, prefix: str, lines: list[str], depth: int,
        file_index: dict, ext_counter: Counter, dir_loc: dict, dir_files: dict,
    ) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in IGNORE_DIRS and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".") and e.suffix not in BINARY_EXTENSIONS]

        rel_dir = str(directory.relative_to(self.root)) if directory != self.root else "."
        for f in files:
            ext = f.suffix.lower()
            ext_counter[ext] += 1
            if ext in SOURCE_EXTENSIONS:
                loc = _count_lines(f)
                dir_loc[rel_dir] += loc
                dir_files[rel_dir] += 1
                file_index[str(f.relative_to(self.root))] = {
                    "size": f.stat().st_size, "loc": loc, "ext": ext,
                    "dir": rel_dir, "name": f.name, "depth": depth,
                    "is_architecture": f.name in ARCHITECTURE_FILE_PATTERNS,
                }

        for i, entry in enumerate(dirs + files):
            is_last = i == len(dirs) + len(files) - 1
            connector = "└── " if is_last else "├── "
            ext_prefix = "    " if is_last else "│   "
            if entry.is_dir():
                sub_loc = _quick_dir_loc(entry)
                ann = f"  [{sub_loc} LOC]" if sub_loc > 0 else ""
                lines.append(f"{prefix}{connector}{entry.name}/{ann}")
                if depth < 6:
                    self._walk_recursive(entry, prefix + ext_prefix, lines, depth + 1,
                                         file_index, ext_counter, dir_loc, dir_files)
                else:
                    _index_deep(self.root, entry, depth + 1, file_index, ext_counter, dir_loc, dir_files)
            else:
                loc = _count_lines(entry) if entry.suffix.lower() in SOURCE_EXTENSIONS else 0
                ann = f"  ({loc}L)" if loc > 0 else ""
                lines.append(f"{prefix}{connector}{entry.name}{ann}")

    # -- Phase 2: File selection (scale-adaptive) ----------------------------

    def _select_files(self, file_index: dict[str, dict], scale: ProjectScale) -> list[str]:
        if scale.read_all:
            return list(file_index.keys())

        scored: list[tuple[str, float]] = []
        for path, info in file_index.items():
            score = 0.0
            if info["is_architecture"]:
                score += 100
            score += min(info["loc"], 500) / 10
            score += max(0, 8 - info["depth"]) * 5
            if "test" in path.lower() or "spec" in path.lower():
                score *= 0.4
            if "migration" in path.lower() or "alembic/versions" in path.lower():
                score *= 0.1
            scored.append((path, score))

        scored.sort(key=lambda x: -x[1])

        if scale.category == ProjectScale.MEDIUM:
            target = min(int(scale.file_count * 0.4), 80)
        else:
            target = min(int(scale.file_count * 0.2), 60)

        selected = set()
        dirs_covered: set[str] = set()
        for p, _ in scored[:target]:
            selected.add(p)
            dirs_covered.add(file_index[p]["dir"])

        for p, info in file_index.items():
            if p not in selected and info["dir"] not in dirs_covered:
                selected.add(p)
                dirs_covered.add(info["dir"])

        return list(selected)

    # -- Phase 3: Read files -------------------------------------------------

    def _read_files(self, paths: list[str], scale: ProjectScale) -> dict[str, str]:
        result: dict[str, str] = {}
        max_chars = scale.max_file_read_chars
        for rel_path in sorted(paths):
            fpath = self.root / rel_path
            if fpath.is_file():
                content = _read_file(fpath, max_chars)
                if content:
                    result[rel_path] = content
        return result

    def _read_config_files(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in CONFIG_FILES:
            fpath = self.root / name
            if fpath.is_file():
                content = _read_file(fpath, 10_000)
                if content:
                    result[name] = content
        return result


# ---------------------------------------------------------------------------
# Standalone helpers (keep class methods thin)
# ---------------------------------------------------------------------------


def _count_lines(filepath: Path) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def _quick_dir_loc(directory: Path) -> int:
    total = 0
    try:
        for f in directory.rglob("*"):
            if f.is_file() and f.suffix.lower() in SOURCE_EXTENSIONS and not any(p in IGNORE_DIRS for p in f.parts):
                total += _count_lines(f)
    except PermissionError:
        pass
    return total


def _index_deep(
    root: Path, directory: Path, depth: int,
    file_index: dict, ext_counter: Counter, dir_loc: dict, dir_files: dict,
) -> None:
    rel_dir = str(directory.relative_to(root))
    try:
        for entry in directory.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if entry.name not in IGNORE_DIRS:
                    _index_deep(root, entry, depth + 1, file_index, ext_counter, dir_loc, dir_files)
            elif entry.is_file() and entry.suffix not in BINARY_EXTENSIONS:
                ext = entry.suffix.lower()
                ext_counter[ext] += 1
                if ext in SOURCE_EXTENSIONS:
                    loc = _count_lines(entry)
                    dir_loc[rel_dir] += loc
                    dir_files[rel_dir] += 1
                    file_index[str(entry.relative_to(root))] = {
                        "size": entry.stat().st_size, "loc": loc, "ext": ext,
                        "dir": rel_dir, "name": entry.name, "depth": depth,
                        "is_architecture": entry.name in ARCHITECTURE_FILE_PATTERNS,
                    }
    except PermissionError:
        pass


def _read_file(fpath: Path, max_chars: int) -> str | None:
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return None
    if len(content) <= max_chars:
        return content
    head_size = max_chars * 2 // 3
    tail_size = max_chars // 3
    omitted = len(content) - head_size - tail_size
    return f"{content[:head_size]}\n\n... ({omitted} chars omitted) ...\n\n{content[-tail_size:]}"


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


async def compute_scan_fingerprint(path: str) -> str:
    """Compute a fingerprint for the codebase state."""
    root = Path(os.path.expanduser(path)).resolve()
    git_dir = root / ".git"
    if git_dir.exists():
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD", cwd=str(root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return f"git:{stdout.decode().strip()}"
        except (OSError, ValueError):
            pass

    h = hashlib.sha256()
    for name in CONFIG_FILES:
        fpath = root / name
        if fpath.is_file():
            try:
                stat = fpath.stat()
                h.update(f"{name}:{stat.st_mtime_ns}:{stat.st_size}".encode())
            except OSError:
                continue
    return f"mtime:{h.hexdigest()[:16]}"
