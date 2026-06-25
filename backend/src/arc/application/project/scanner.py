"""Codebase scanner — full project understanding.

Scans EVERYTHING that's human-readable in the project: code, docs, configs,
CI/CD, k8s, scripts, tests. Only skips binary files and build artifacts.

No hardcoded file-type classifications. No scoring formulas. No fixed budgets.
The scanner reads the project as a whole, adapts to its scale, and gives the
LLM the full picture to reason about.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Only skip: binary files and build artifact directories
# These are the only hardcoded exclusions — they are NEVER useful to read.
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".tox", "coverage", ".cache",
    "vendor", "Pods", ".gradle", "out", ".egg-info", "htmlcov",
    ".ruff_cache", ".turbo", ".parcel-cache", ".svelte-kit",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".br", ".bz2", ".xz",
    ".wasm", ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".db", ".sqlite", ".sqlite3",
    ".lock", ".sum",  # lock files are machine-generated
}


# ---------------------------------------------------------------------------
# Project scale — determines how much to read (not WHAT to read)
# ---------------------------------------------------------------------------


class ProjectScale:
    SMALL = "small"      # < 50 text files — read everything
    MEDIUM = "medium"    # 50 - 500 text files
    LARGE = "large"      # > 500 text files

    def __init__(self, total_files: int, total_loc: int):
        self.file_count = total_files
        self.total_loc = total_loc
        if total_files < 50:
            self.category = self.SMALL
        elif total_files <= 500:
            self.category = self.MEDIUM
        else:
            self.category = self.LARGE

    @property
    def read_all(self) -> bool:
        return self.category == self.SMALL

    @property
    def max_file_read_chars(self) -> int:
        """Per-file read limit — adapts to scale."""
        if self.category == self.SMALL:
            return 30_000
        elif self.category == self.MEDIUM:
            return 8_000
        return 5_000

    @property
    def max_tokens(self) -> int:
        """LLM output budget — adapts to scale."""
        if self.category == self.SMALL:
            return 6000
        elif self.category == self.MEDIUM:
            return 8192
        return 10000

    def __repr__(self) -> str:
        return f"ProjectScale({self.category}: {self.file_count} files, {self.total_loc} LOC)"


# ---------------------------------------------------------------------------
# CodebaseScanner — reads the full project
# ---------------------------------------------------------------------------


class CodebaseScanner:
    def __init__(self, path: str):
        self.root = Path(os.path.expanduser(path)).resolve()
        if not self.root.is_dir():
            raise ValueError(f"路径不存在或不是目录: {self.root}")

    def full_scan(self) -> dict:
        """Scan everything: structure + docs + configs + code + scripts + CI."""
        tree_lines, file_index, stats = self._walk_full()
        scale = ProjectScale(stats["total_files"], stats["total_loc"])
        files_to_read = self._select_files(file_index, scale)
        file_contents = self._read_files(files_to_read, scale)
        return {
            "path": str(self.root),
            "tree": "\n".join(tree_lines),
            "stats": stats,
            "scale": scale,
            "source_files": file_contents,  # all readable content (code+docs+config)
            "config_files": {},  # kept for interface compat, merged into source_files
            "file_index": file_index,
        }

    # -- Phase 1: Walk everything, index all text files ----------------------

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
        total_files = len(file_index)
        total_loc = sum(dir_loc.values())

        stats = {
            "total_files": total_files,
            "total_source_files": total_files,  # compat
            "total_loc": total_loc,
            "extensions": ext_counter.most_common(30),
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

        dirs = [
            e for e in entries
            if e.is_dir()
            and e.name not in IGNORE_DIRS
            and not (e.name.startswith(".")
                     and e.name not in (".github", ".circleci", ".gitlab"))
        ]
        files = [
            e for e in entries
            if e.is_file()
            and not e.name.startswith(".")
            and e.suffix.lower() not in BINARY_EXTENSIONS
        ]

        rel_dir = str(directory.relative_to(self.root)) if directory != self.root else "."

        for f in files:
            ext = f.suffix.lower()
            ext_counter[ext] += 1
            try:
                size = f.stat().st_size
            except OSError:
                continue
            # Skip files > 1MB (likely generated/minified)
            if size > 1_000_000:
                continue
            loc = _count_lines(f)
            dir_loc[rel_dir] += loc
            dir_files[rel_dir] += 1
            file_index[str(f.relative_to(self.root))] = {
                "size": size, "loc": loc, "ext": ext,
                "dir": rel_dir, "name": f.name, "depth": depth,
            }

        # Build tree display
        all_items = dirs + files
        for i, entry in enumerate(all_items):
            is_last = i == len(all_items) - 1
            connector = "└── " if is_last else "├── "
            ext_prefix = "    " if is_last else "│   "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                if depth < 6:
                    self._walk_recursive(entry, prefix + ext_prefix, lines, depth + 1,
                                         file_index, ext_counter, dir_loc, dir_files)
                else:
                    _index_deep(self.root, entry, depth + 1,
                                file_index, ext_counter, dir_loc, dir_files)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    # -- Phase 2: File selection — read all or by coverage -------------------

    def _select_files(self, file_index: dict[str, dict], scale: ProjectScale) -> list[str]:
        """Select files to read. Small projects: all.
    Larger: ensure every directory is represented."""
        if scale.read_all:
            return list(file_index.keys())

        # For medium/large: pick the most substantial file from each directory,
        # plus all files from directories with few files (they're likely important configs/docs)
        selected: set[str] = set()
        dir_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)

        for path, info in file_index.items():
            dir_groups[info["dir"]].append((path, info))

        for dir_path, files in dir_groups.items():
            # Directories with ≤ 5 files: read all (likely config/docs/scripts)
            if len(files) <= 5:
                for path, _ in files:
                    selected.add(path)
            else:
                # Larger directories: sort by size (larger = more content), take proportional sample
                files.sort(key=lambda x: -x[1]["size"])
                # Take sqrt(n) files — scales sublinearly
                sample_size = max(3, int(len(files) ** 0.5))
                for path, _ in files[:sample_size]:
                    selected.add(path)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_lines(filepath: Path) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


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
            elif entry.is_file() and entry.suffix.lower() not in BINARY_EXTENSIONS:
                ext = entry.suffix.lower()
                ext_counter[ext] += 1
                try:
                    size = entry.stat().st_size
                except OSError:
                    continue
                if size > 1_000_000:
                    continue
                loc = _count_lines(entry)
                dir_loc[rel_dir] += loc
                dir_files[rel_dir] += 1
                file_index[str(entry.relative_to(root))] = {
                    "size": size, "loc": loc, "ext": ext,
                    "dir": rel_dir, "name": entry.name, "depth": depth,
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
    for fpath in sorted(root.rglob("*"))[:100]:
        if fpath.is_file() and fpath.suffix.lower() not in BINARY_EXTENSIONS:
            try:
                stat = fpath.stat()
                h.update(f"{fpath.name}:{stat.st_mtime_ns}:{stat.st_size}".encode())
            except OSError:
                continue
    return f"mtime:{h.hexdigest()[:16]}"
