"""全量产品原型聚合 — 合并项目/版本所有需求的原型页面为统一预览。

聚合逻辑:
1. 查询项目或版本下所有 prototype 类型 artifact（按 todo 创建时间排序）
2. 合并 pages（同名页面以最新版本为准）
3. 标记当前请求 todo 的页面为 is_new
4. 生成带导航栏的完整 shell HTML

发布逻辑:
- publish_bundle() 将聚合包上传到 S3
- 路径: previews/projects/{project_id}/{version_id}/latest/ 或 snapshots/{timestamp}/
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

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


# 复用 publish_service 中的常量
INTERCEPTOR_SCRIPT = """<script>
document.addEventListener('click',function(e){
  var t=e.target.closest('a,button,[role="button"],[onclick]');
  if(!t)return;
  var href=t.getAttribute('href')||'';
  if(href.startsWith('http')||href.startsWith('mailto'))return;
  e.preventDefault();e.stopPropagation();
  window.parent.postMessage({type:'nav',text:t.textContent.trim(),href:href},'*');
},true);
document.addEventListener('submit',function(e){
  e.preventDefault();
  var btn=e.target.querySelector('[type=submit],button');
  window.parent.postMessage({type:'nav',text:btn?btn.textContent.trim():'提交',href:e.target.action||''},'*');
},true);
</script>"""

CSP_META = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' \'unsafe-inline\' data: blob:; script-src \'unsafe-inline\'; connect-src \'none\';">'


class PrototypeBundleService:
    """聚合项目/版本下所有原型为统一预览。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._artifact_repo = ArtifactRepository(db)
        self._todo_repo = TodoRepository(db)

    async def build_bundle(
        self,
        project_id: uuid.UUID,
        *,
        version_id: uuid.UUID | None = None,
        current_todo_id: uuid.UUID | None = None,
    ) -> PrototypeBundle:
        """构建项目/版本全量原型包。

        Args:
            project_id: 项目 ID
            version_id: 版本 ID（有值时只聚合该版本的 prototype）
            current_todo_id: 当前需求 ID（其页面标记为 NEW）
        """
        # 按版本或项目查询 artifacts
        if version_id:
            artifacts = await self._artifact_repo.list_by_version_and_type(
                version_id, ArtifactType.PROTOTYPE
            )
        else:
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

    async def publish_bundle(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        snapshot: bool = False,
        current_todo_id: uuid.UUID | None = None,
    ) -> str | None:
        """将版本原型聚合包上传到 S3，返回 public URL。

        Args:
            project_id: 项目 ID
            version_id: 版本 ID
            snapshot: True 时生成不可变快照（版本 release 时调用）
            current_todo_id: 标记新增页面

        Returns:
            index.html 的 public URL，或 None（无页面时）
        """
        from arc.infrastructure.storage import get_storage

        bundle = await self.build_bundle(
            project_id, version_id=version_id, current_todo_id=current_todo_id
        )
        if not bundle.pages:
            return None

        storage = get_storage()

        # 确定 S3 前缀
        if snapshot:
            ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            prefix = f"previews/projects/{project_id}/{version_id}/snapshots/{ts}"
        else:
            prefix = f"previews/projects/{project_id}/{version_id}/latest"
            # 清除旧的 latest
            await storage.async_delete_prefix(prefix)

        # 上传每个页面
        slugs: list[str] = []
        names: list[str] = []
        for i, page in enumerate(bundle.pages):
            slug = f"page_{i}"
            html = page.html

            # 注入 CSP
            if "<head>" in html:
                html = html.replace("<head>", f"<head>{CSP_META}", 1)

            # 注入 interceptor script
            if "</body>" in html:
                html = html.replace("</body>", INTERCEPTOR_SCRIPT + "</body>")
            else:
                html += INTERCEPTOR_SCRIPT

            await storage.async_upload(
                f"{prefix}/pages/{slug}.html",
                html.encode("utf-8"),
                "text/html; charset=utf-8",
            )
            slugs.append(slug)
            names.append(page.name)

        # 生成 shell HTML (S3 版本使用相对路径)
        shell_html = self._build_s3_shell(slugs, names)
        await storage.async_upload(
            f"{prefix}/index.html",
            shell_html.encode("utf-8"),
            "text/html; charset=utf-8",
        )

        # 构造 public URL
        from arc.config import settings

        if settings.storage_public_url:
            base = settings.storage_public_url.rstrip("/")
        elif settings.storage_endpoint:
            base = f"{settings.storage_endpoint}/{settings.storage_bucket}"
        else:
            base = "/static/previews"

        public_url = f"{base}/{prefix}/index.html"
        logger.info(
            "Published prototype bundle: project=%s version=%s snapshot=%s → %s (%d pages)",
            project_id, version_id, snapshot, public_url, len(bundle.pages),
        )

        # 非 snapshot 模式同时覆盖 latest
        if snapshot:
            # snapshot 时也更新 latest 指向同一内容
            latest_prefix = f"previews/projects/{project_id}/{version_id}/latest"
            await storage.async_delete_prefix(latest_prefix)
            for i, page in enumerate(bundle.pages):
                slug = f"page_{i}"
                html = page.html
                if "<head>" in html:
                    html = html.replace("<head>", f"<head>{CSP_META}", 1)
                if "</body>" in html:
                    html = html.replace("</body>", INTERCEPTOR_SCRIPT + "</body>")
                else:
                    html += INTERCEPTOR_SCRIPT
                await storage.async_upload(
                    f"{latest_prefix}/pages/{slug}.html",
                    html.encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            await storage.async_upload(
                f"{latest_prefix}/index.html",
                shell_html.encode("utf-8"),
                "text/html; charset=utf-8",
            )

        return public_url

    async def persist_to_project(
        self,
        project_id: uuid.UUID,
        current_todo_id: uuid.UUID | None = None,
    ) -> str | None:
        """将项目全量原型持久化到项目本地目录（legacy 兼容）。

        写入路径: {project.local_path}/.arc/prototype/index.html
        每个页面额外写入独立 HTML: {project.local_path}/.arc/prototype/pages/{name}.html

        Returns:
            站点目录路径，或 None（项目无 local_path）。
        """
        from pathlib import Path
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self._db).get_by_id(project_id)
        if not project or not project.local_path:
            return None

        bundle = await self.build_bundle(project_id, current_todo_id=current_todo_id)
        if not bundle.pages:
            return None

        site_dir = Path(project.local_path) / ".arc" / "prototype"
        pages_dir = site_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        # 写入聚合 shell
        (site_dir / "index.html").write_text(bundle.shell_html, encoding="utf-8")

        # 写入每个页面独立 HTML（方便引用和部署）
        for page in bundle.pages:
            safe_name = page.name.replace("/", "_").replace(" ", "_")
            page_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<style>body{{margin:0;padding:16px;background:#1E1E2E;color:#E8E6E3;font-family:system-ui,sans-serif}}*{{box-sizing:border-box}}</style>
</head><body>{page.html}</body></html>"""
            (pages_dir / f"{safe_name}.html").write_text(page_html, encoding="utf-8")

        logger.info(
            "Persisted prototype site for project %s: %d pages → %s",
            project_id, len(bundle.pages), site_dir,
        )
        return str(site_dir)

    @staticmethod
    def _build_shell(pages: list[BundlePage]) -> str:
        """生成带导航栏的完整 HTML shell（内嵌 pages，用于动态渲染）。"""
        if not pages:
            return ""

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

    @staticmethod
    def _build_s3_shell(slugs: list[str], names: list[str]) -> str:
        """生成 S3 版 shell HTML（使用相对路径引用页面文件）。"""
        slugs_json = json.dumps(slugs)
        names_json = json.dumps(names, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>产品预览</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{height:100vh;display:flex;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
.toolbar{{display:flex;align-items:center;padding:0 12px;height:40px;background:#1e1e2e;gap:8px;flex-shrink:0}}
.toolbar .back{{background:none;border:none;color:#888;cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px}}
.toolbar .back:hover{{background:#2a2a3a;color:#fff}}
.toolbar .back:disabled{{opacity:.3;cursor:default}}
.toolbar .title{{color:#e0e0e0;font-size:12px;font-weight:500;flex:1;text-align:center}}
.toolbar .pages-btn{{background:#2a2a3a;border:1px solid #3a3a4a;color:#aaa;font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer}}
.toolbar .pages-btn:hover{{background:#3a3a4a;color:#fff}}
.page-list{{position:absolute;top:40px;right:8px;background:#1e1e2e;border:1px solid #3a3a4a;border-radius:8px;padding:4px;z-index:100;display:none;min-width:160px;box-shadow:0 8px 24px rgba(0,0,0,.4)}}
.page-list.open{{display:block}}
.page-list button{{display:block;width:100%;text-align:left;background:none;border:none;color:#ccc;padding:8px 12px;font-size:11px;border-radius:4px;cursor:pointer}}
.page-list button:hover{{background:#2a2a3a}}
.page-list button.active{{background:#6366f1;color:#fff}}
.frame{{flex:1;border:none;width:100%}}
.toast{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
</style></head><body>
<div class="toolbar">
  <button class="back" id="btn-back" onclick="goBack()" disabled>&larr;</button>
  <span class="title" id="page-title"></span>
  <button class="pages-btn" onclick="togglePages()">全部页面</button>
</div>
<div class="page-list" id="page-list"></div>
<iframe id="frame" class="frame" sandbox="allow-scripts allow-forms"></iframe>
<div class="toast" id="toast"></div>
<script>
var slugs={slugs_json};
var names={names_json};
var cur=0,hist=[0],hIdx=0;

function render(){{
  document.getElementById('frame').src='pages/'+slugs[cur]+'.html';
  document.getElementById('page-title').textContent=names[cur];
  document.getElementById('btn-back').disabled=hIdx<=0;
  renderPageList();
}}

function navigateTo(i){{
  if(i<0||i>=slugs.length||i===cur)return;
  cur=i;hist=hist.slice(0,hIdx+1);hist.push(i);hIdx=hist.length-1;render();
}}

function goBack(){{if(hIdx>0){{hIdx--;cur=hist[hIdx];render();}}}}

function findPage(text,href){{
  var t=text.toLowerCase().replace(/\\s/g,'');
  var best=-1,bestScore=0;
  for(var i=0;i<names.length;i++){{
    var n=names[i].toLowerCase();
    var score=0;
    if(t===n)score=100;
    else if(t.includes(n)||n.includes(t))score=80;
    else{{for(var ci=0;ci<n.length;ci++){{if(t.includes(n[ci]))score+=10;}}}}
    if(score>bestScore){{bestScore=score;best=i;}}
  }}
  if(best>=0&&bestScore>=20)return best;
  return(cur+1)%slugs.length;
}}

function togglePages(){{document.getElementById('page-list').classList.toggle('open');}}
function renderPageList(){{
  var el=document.getElementById('page-list');
  el.innerHTML=names.map(function(n,i){{
    return '<button class="'+(i===cur?'active':'')+'" onclick="navigateTo('+i+');togglePages()">'+n+'</button>';
  }}).join('');
}}

function showToast(msg){{
  var el=document.getElementById('toast');
  el.textContent=msg;el.classList.add('show');
  setTimeout(function(){{el.classList.remove('show');}},1500);
}}

window.addEventListener('message',function(e){{
  if(e.data&&e.data.type==='nav'){{
    var idx=findPage(e.data.text,e.data.href);
    if(idx===cur){{showToast('当前已在: '+names[cur]);}}
    else{{navigateTo(idx);showToast('跳转到: '+names[idx]);}}
  }}
}});

document.addEventListener('click',function(e){{
  if(!e.target.closest('.page-list,.pages-btn'))
    document.getElementById('page-list').classList.remove('open');
}});

render();
</script></body></html>"""
