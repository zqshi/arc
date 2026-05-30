/**
 * 原型预览工具函数 — 在新标签页中打开原型 HTML 预览。
 * 从 ConversationModeView.tsx 提取。
 */

export function openPrototypeInNewTab(content: Record<string, unknown>) {
  const pages = (content.pages || []) as Array<{ name?: string; html?: string }>;
  if (pages.length === 0) return;

  const interceptorScript = `<script>
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
<\/script>`;

  const blobUrls = pages.map((p) => {
    let html = p.html || '';
    if (html.includes('</body>')) {
      html = html.replace('</body>', interceptorScript + '</body>');
    } else {
      html += interceptorScript;
    }
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    return URL.createObjectURL(blob);
  });

  const names = pages.map((p, i) => p.name || `页面${i + 1}`);
  const urlsJson = JSON.stringify(blobUrls);
  const namesJson = JSON.stringify(names);

  const shell = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>产品预览</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{height:100vh;display:flex;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
.toolbar{display:flex;align-items:center;padding:0 12px;height:40px;background:#1e1e2e;gap:8px;flex-shrink:0}
.toolbar .back{background:none;border:none;color:#888;cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px}
.toolbar .back:hover{background:#2a2a3a;color:#fff}
.toolbar .back:disabled{opacity:.3;cursor:default}
.toolbar .title{color:#e0e0e0;font-size:12px;font-weight:500;flex:1;text-align:center}
.toolbar .pages-btn{background:#2a2a3a;border:1px solid #3a3a4a;color:#aaa;font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer}
.toolbar .pages-btn:hover{background:#3a3a4a;color:#fff}
.page-list{position:absolute;top:40px;right:8px;background:#1e1e2e;border:1px solid #3a3a4a;border-radius:8px;padding:4px;z-index:100;display:none;min-width:160px;box-shadow:0 8px 24px rgba(0,0,0,.4)}
.page-list.open{display:block}
.page-list button{display:block;width:100%;text-align:left;background:none;border:none;color:#ccc;padding:8px 12px;font-size:11px;border-radius:4px;cursor:pointer}
.page-list button:hover{background:#2a2a3a}
.page-list button.active{background:#6366f1;color:#fff}
.frame{flex:1;border:none;width:100%}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .3s;pointer-events:none}
.toast.show{opacity:1}
</style></head><body>
<div class="toolbar">
  <button class="back" id="btn-back" onclick="goBack()" disabled>&larr;</button>
  <span class="title" id="page-title"></span>
  <button class="pages-btn" onclick="togglePages()">全部页面</button>
</div>
<div class="page-list" id="page-list"></div>
<iframe id="frame" class="frame"></iframe>
<div class="toast" id="toast"></div>
<script>
var urls=${urlsJson};
var names=${namesJson};
var cur=0,hist=[0],hIdx=0;

function render(){
  document.getElementById('frame').src=urls[cur];
  document.getElementById('page-title').textContent=names[cur];
  document.getElementById('btn-back').disabled=hIdx<=0;
  renderPageList();
}

function navigateTo(i){
  if(i<0||i>=urls.length||i===cur)return;
  cur=i;
  hist=hist.slice(0,hIdx+1);
  hist.push(i);
  hIdx=hist.length-1;
  render();
}

function goBack(){
  if(hIdx>0){hIdx--;cur=hist[hIdx];render();}
}

function findPage(text,href){
  var t=text.toLowerCase().replace(/\\s/g,'');
  var h=(href||'').toLowerCase();
  var best=-1,bestScore=0;
  for(var i=0;i<names.length;i++){
    var n=names[i].replace(/页$/,'').replace(/面$/,'').toLowerCase();
    if(!n)continue;
    var score=0;
    if(t===n||t===names[i].toLowerCase())score=100;
    else if(t.includes(n)||n.includes(t))score=80;
    else{for(var ci=0;ci<n.length;ci++){if(t.includes(n[ci]))score+=10;}}
    var hmap={'login':'登录','register':'注册','signup':'注册','home':'首页','dashboard':'工作台','list':'列表','detail':'详情','chat':'对话','setting':'设置','profile':'个人'};
    for(var k in hmap){if(h.includes(k)&&names[i].includes(hmap[k]))score+=60;}
    if(score>bestScore){bestScore=score;best=i;}
  }
  if(best>=0&&bestScore>=20)return best;
  return(cur+1)%urls.length;
}

function togglePages(){document.getElementById('page-list').classList.toggle('open');}

function renderPageList(){
  var el=document.getElementById('page-list');
  el.innerHTML=names.map(function(n,i){
    return '<button class="'+(i===cur?'active':'')+'" onclick="navigateTo('+i+');togglePages()">'+n+'</button>';
  }).join('');
}

function showToast(msg){
  var el=document.getElementById('toast');
  el.textContent=msg;el.classList.add('show');
  setTimeout(function(){el.classList.remove('show');},1500);
}

window.addEventListener('message',function(e){
  if(e.data&&e.data.type==='nav'){
    var idx=findPage(e.data.text,e.data.href);
    if(idx===cur){showToast('当前已在: '+names[cur]);}
    else{navigateTo(idx);showToast('跳转到: '+names[idx]);}
  }
});

document.addEventListener('click',function(e){
  if(!e.target.closest('.page-list,.pages-btn'))
    document.getElementById('page-list').classList.remove('open');
});

render();
</script></body></html>`;

  const shellBlob = new Blob([shell], { type: 'text/html;charset=utf-8' });
  const shellUrl = URL.createObjectURL(shellBlob);
  window.open(shellUrl, '_blank');
  setTimeout(() => {
    URL.revokeObjectURL(shellUrl);
    blobUrls.forEach((u) => URL.revokeObjectURL(u));
  }, 60_000);
}
