"""原型发布服务 — 将 prototype artifact 的 HTML 页面上传到对象存储。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.errors import AppError, NotFoundError
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

SHELL_TEMPLATE = """<!DOCTYPE html>
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
var baseUrl="{base_url}";
var slugs={slugs_json};
var names={names_json};
var cur=0,hist=[0],hIdx=0;

function render(){{
  document.getElementById('frame').src=baseUrl+'/'+slugs[cur]+'.html';
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


class PublishService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ArtifactRepository(db)

    async def publish_prototype(self, artifact_id: uuid.UUID) -> str:
        artifact = await self.repo.get_by_id(artifact_id)
        if not artifact:
            raise NotFoundError("Artifact not found")
        if artifact.artifact_type != ArtifactType.PROTOTYPE:
            raise AppError("Only prototype artifacts can be published")

        pages = artifact.content.get("pages", [])
        if not pages:
            raise AppError("Prototype has no pages")

        storage = get_storage()
        prefix = f"previews/{artifact.todo_id}/{artifact.id}"

        # Clean old objects before republish
        await storage.async_delete_prefix(prefix)

        slugs = []
        names = []
        for i, page in enumerate(pages):
            name = page.get("name", f"页面{i + 1}")
            slug = f"page_{i}"
            html = page.get("html", "")

            if "<head>" in html:
                html = html.replace("<head>", f"<head>{CSP_META}", 1)
            elif "<html" in html:
                html = html.replace("<html", f"<html><head>{CSP_META}</head><html", 1).replace("<html><head>", f"<head>{CSP_META}</head>", 1)

            if "</body>" in html:
                html = html.replace("</body>", INTERCEPTOR_SCRIPT + "</body>")
            else:
                html += INTERCEPTOR_SCRIPT

            await storage.async_upload(f"{prefix}/{slug}.html", html.encode("utf-8"), "text/html; charset=utf-8")
            slugs.append(slug)
            names.append(name)

        import json
        shell_html = SHELL_TEMPLATE.format(
            base_url=f"{self._get_public_base()}/{prefix}",
            slugs_json=json.dumps(slugs),
            names_json=json.dumps(names),
        )
        await storage.async_upload(f"{prefix}/index.html", shell_html.encode("utf-8"), "text/html; charset=utf-8")

        public_url = f"{self._get_public_base()}/{prefix}/index.html"
        artifact.set_preview_url(public_url)
        await self.repo.update(artifact)

        logger.info("Published prototype %s → %s", artifact_id, public_url)
        return public_url

    async def unpublish_prototype(self, artifact_id: uuid.UUID) -> None:
        """Remove published files from storage and clear preview_url."""
        artifact = await self.repo.get_by_id(artifact_id)
        if not artifact:
            return

        if artifact.preview_url:
            storage = get_storage()
            prefix = f"previews/{artifact.todo_id}/{artifact.id}"
            deleted = await storage.async_delete_prefix(prefix)
            logger.info("Unpublished artifact %s, deleted %d objects", artifact_id, deleted)

            artifact.set_preview_url(None)
            await self.repo.update(artifact)

    @staticmethod
    def _get_public_base() -> str:
        from arc.config import settings
        if settings.storage_public_url:
            return settings.storage_public_url.rstrip("/")
        if settings.storage_endpoint:
            return f"{settings.storage_endpoint}/{settings.storage_bucket}"
        return "/static/previews"
