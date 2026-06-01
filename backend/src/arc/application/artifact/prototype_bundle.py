"""全量产品原型聚合 — 合并项目所有需求的原型页面为统一预览。

聚合逻辑:
1. 查询项目下所有 prototype 类型 artifact（按 todo 创建时间排序）
2. 合并 pages（同名页面以最新版本为准）
3. 标记当前请求 todo 的页面为 is_new
4. 生成带导航栏的完整 shell HTML
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


@dataclass
class BundlePage:
    """聚合后的单个页面。"""

    name: str
    html: str
    source_todo_id: str
    source_todo_title: str
    is_new: bool = False


@dataclass
class PrototypeBundle:
    """项目级全量原型包。"""

    pages: list[BundlePage] = field(default_factory=list)
    shell_html: str = ""
    total_pages: int = 0
    new_pages: int = 0


class PrototypeBundleService:
    """聚合项目下所有原型为统一预览。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._artifact_repo = ArtifactRepository(db)
        self._todo_repo = TodoRepository(db)

    async def build_bundle(
        self,
        project_id: uuid.UUID,
        current_todo_id: uuid.UUID | None = None,
    ) -> PrototypeBundle:
        """构建项目全量原型包。

        Args:
            project_id: 项目 ID
            current_todo_id: 当前需求 ID（其页面标记为 NEW）
        """
        # 获取项目下所有 prototype artifacts
        artifacts = await self._artifact_repo.list_by_project_and_type(
            project_id, ArtifactType.PROTOTYPE
        )

        if not artifacts:
            return PrototypeBundle()

        # 收集每个 artifact 对应的 todo title
        todo_titles: dict[str, str] = {}
        for art in artifacts:
            if art.todo_id and str(art.todo_id) not in todo_titles:
                todo = await self._todo_repo.get_by_id(art.todo_id)
                todo_titles[str(art.todo_id)] = todo.title if todo else "未知需求"

        # 合并 pages — 同名页面以最新版本为准
        page_map: dict[str, BundlePage] = {}

        # 按创建时间正序（旧的先加入，新的覆盖）
        sorted_artifacts = sorted(artifacts, key=lambda a: a.created_at)

        for art in sorted_artifacts:
            content = art.content or {}
            pages = content.get("pages", [])
            todo_id_str = str(art.todo_id) if art.todo_id else ""
            todo_title = todo_titles.get(todo_id_str, "未知需求")
            is_current = current_todo_id and art.todo_id == current_todo_id

            for page in pages:
                name = page.get("name", "").strip()
                html = page.get("html", "")
                if not name or not html:
                    continue

                page_map[name] = BundlePage(
                    name=name,
                    html=html,
                    source_todo_id=todo_id_str,
                    source_todo_title=todo_title,
                    is_new=bool(is_current),
                )

        bundle_pages = list(page_map.values())
        new_count = sum(1 for p in bundle_pages if p.is_new)

        # 生成 shell HTML
        shell_html = self._build_shell(bundle_pages)

        return PrototypeBundle(
            pages=bundle_pages,
            shell_html=shell_html,
            total_pages=len(bundle_pages),
            new_pages=new_count,
        )

    @staticmethod
    def _build_shell(pages: list[BundlePage]) -> str:
        """生成带导航栏的完整 HTML shell。"""
        if not pages:
            return "<html><body><p>暂无原型页面</p></body></html>"

        # 页面数据
        pages_json = json.dumps(
            [{"name": p.name, "html": p.html, "isNew": p.is_new, "source": p.source_todo_title}
             for p in pages],
            ensure_ascii=False,
        )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>产品预览</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ height: 100vh; display: flex; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f0f1a; color: #e0e0e0; }}
.sidebar {{ width: 220px; background: #1a1b2e; border-right: 1px solid #2a2b3e; display: flex; flex-direction: column; flex-shrink: 0; }}
.sidebar-header {{ padding: 16px; border-bottom: 1px solid #2a2b3e; }}
.sidebar-header h1 {{ font-size: 14px; font-weight: 600; color: #fff; }}
.sidebar-header p {{ font-size: 11px; color: #888; margin-top: 4px; }}
.nav-list {{ flex: 1; overflow-y: auto; padding: 8px; }}
.nav-item {{ display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 12px; color: #aaa; transition: all 0.15s; }}
.nav-item:hover {{ background: #2a2b3e; color: #fff; }}
.nav-item.active {{ background: #3b82f6/15; color: #60a5fa; border: 1px solid #3b82f620; }}
.nav-item .badge {{ font-size: 9px; padding: 2px 6px; border-radius: 4px; background: #10b981; color: #fff; font-weight: 600; }}
.nav-item .source {{ font-size: 9px; color: #666; display: block; margin-top: 2px; }}
.content {{ flex: 1; display: flex; flex-direction: column; }}
.content iframe {{ flex: 1; border: 0; background: #1e1e2e; }}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <h1>🎨 产品预览</h1>
    <p id="page-count"></p>
  </div>
  <div class="nav-list" id="nav-list"></div>
</div>
<div class="content">
  <iframe id="preview-frame" sandbox="allow-scripts"></iframe>
</div>
<script>
const pages = {pages_json};
const navList = document.getElementById('nav-list');
const frame = document.getElementById('preview-frame');
const pageCount = document.getElementById('page-count');

const newCount = pages.filter(p => p.isNew).length;
pageCount.textContent = pages.length + ' 个页面' + (newCount > 0 ? '，' + newCount + ' 个新增' : '');

let activeIdx = 0;

function renderNav() {{
  navList.innerHTML = '';
  pages.forEach((p, i) => {{
    const item = document.createElement('div');
    item.className = 'nav-item' + (i === activeIdx ? ' active' : '');
    item.innerHTML = '<div style="flex:1"><span>' + p.name + '</span>'
      + (p.isNew ? ' <span class="badge">NEW</span>' : '')
      + '<span class="source">' + p.source + '</span></div>';
    item.onclick = () => {{ activeIdx = i; renderNav(); showPage(i); }};
    navList.appendChild(item);
  }});
}}

function showPage(idx) {{
  const p = pages[idx];
  const html = '<!DOCTYPE html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"><\\/script><style>body{{margin:0;padding:16px;background:#1E1E2E;color:#E8E6E3;font-family:system-ui,sans-serif}}*{{box-sizing:border-box}}</style></head><body>' + p.html + '</body></html>';
  frame.srcdoc = html;
}}

renderNav();
showPage(0);
</script>
</body>
</html>"""
