import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  FileText,
  Lightbulb,
  Loader2,
  ChevronRight,
  CheckCircle2,
  Circle,
  ExternalLink,
} from 'lucide-react';
import { useConversationSocket } from '../../hooks/useConversationSocket';
import { useToast } from '../../components/Toast';
import { api } from '../../api/client';
import ExperienceDetailModal from '../../components/ExperienceDetailModal';
import DeliverableDrawer from '../../components/DeliverableDrawer';
import { ChatInput, ChatMessages } from '../../components/todo';
import type {
  Todo,
  Experience,
  DeliverableTracker,
  Conversation,
  Artifact,
} from '../../types/api';

const DELIVERABLE_LABELS: Record<string, string> = {
  requirement_spec: '需求规格',
  interaction_design: '交互设计',
  ui_spec: '视觉规范',
  prototype: '原型设计',
  tech_architecture: '技术架构',
  dev_report: '开发报告',
  test_report: '测试报告',
  deploy_report: '部署报告',
  experience_card: '经验卡片',
  // Legacy
  ui_design: 'UI设计(旧)',
};

export function ConversationModeView({ todo, setTodo, isNarrow, isCompact }: {
  todo: Todo; setTodo: (t: Todo) => void; isNarrow: boolean; isCompact: boolean;
}) {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const [inputValue, setInputValue] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [tracker, setTracker] = useState<DeliverableTracker | null>(null);
  const [initializing, setInitializing] = useState(false);
  const [showRight, setShowRight] = useState(!isNarrow);
  const [relatedExps, setRelatedExps] = useState<Experience[]>([]);
  const [selectedExp, setSelectedExp] = useState<Experience | null>(null);
  const [drawerArtifact, setDrawerArtifact] = useState<Artifact | null>(null);

  const {
    messages: wsMessages,
    isConnected,
    isStreaming,
    error: wsError,
    sendMessage: wsSend,
    retry: wsRetry,
    retryDisabled: wsRetryDisabled,
    artifactsVersion,
  } = useConversationSocket(conversationId);

  const fetchTracker = useCallback(async () => {
    if (!id) return;
    try {
      const state = await api.getDeliverables(id);
      setTracker(state);
    } catch { /* fetch failed, keep previous state */ }
  }, [id]);

  const autoInitRef = useRef(false);

  const fetchConversation = useCallback(async () => {
    if (!id) return;
    try {
      const conversations = await api.listConversations(id);
      const unified = conversations.find((c: Conversation) => c.purpose === 'unified');
      if (unified) {
        setConversationId(unified.id);
      } else if (!autoInitRef.current) {
        autoInitRef.current = true;
        setInitializing(true);
        try {
          const updated = await api.startConversation(id);
          setTodo(updated);
          const convs = await api.listConversations(id);
          const newUnified = convs.find((c: Conversation) => c.purpose === 'unified');
          if (newUnified) setConversationId(newUnified.id);
          await fetchTracker();
        } catch (err) {
          toast(`初始化对话失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
        } finally {
          setInitializing(false);
        }
      }
    } catch { /* fetch failed, keep previous state */ }
  }, [id, fetchTracker, toast, setTodo]);

  useEffect(() => {
    fetchConversation();
    fetchTracker();
  }, [fetchConversation, fetchTracker]);

  useEffect(() => {
    if (!todo) return;
    api.searchExperiences(todo.title, todo.project_id || undefined)
      .then(setRelatedExps).catch(() => setRelatedExps([]));
  }, [todo?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isStreaming && conversationId) fetchTracker();
  }, [isStreaming, conversationId, fetchTracker]);

  useEffect(() => {
    if (artifactsVersion > 0) fetchTracker();
  }, [artifactsVersion, fetchTracker]);

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    wsSend(trimmed);
    setInputValue('');
  };

  const isReady = !!conversationId;

  return (
    <>
      <div className="flex flex-1 overflow-hidden">
        {/* Center: Chat */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {isReady ? (
            <>
              {tracker && (
                <div className="flex items-center gap-2 border-b border-border/50 px-4 py-1.5">
                  <div className="h-1 w-20 overflow-hidden rounded-full bg-border">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${tracker.completion_pct * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-text-muted">{Math.round(tracker.completion_pct * 100)}%</span>
                </div>
              )}
              <div className="flex-1 overflow-y-auto px-4 py-3">
                <ChatMessages
                  messages={wsMessages}
                  isStreaming={isStreaming}
                  error={wsError}
                  conversationId={conversationId}
                  todoId={id!}
                  onRetry={wsRetry}
                  retryDisabled={wsRetryDisabled}
                />
              </div>
              <div className="border-t border-border px-4 py-2.5">
                <ChatInput value={inputValue} onChange={setInputValue} onSend={handleSend} disabled={!isConnected} />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <Loader2 size={20} className="animate-spin text-accent" />
                <span className="text-xs text-text-muted">{initializing ? '正在初始化对话...' : '加载中...'}</span>
              </div>
            </div>
          )}
        </div>

        {/* Right: Deliverables panel */}
        {!isCompact && (showRight ? (
          <div className="flex w-[260px] flex-shrink-0 flex-col border-l border-border bg-bg-sidebar">
            <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
              <div className="flex items-center gap-2">
                <FileText size={13} className="text-accent" />
                <span className="text-xs font-medium text-text-primary">交付物</span>
              </div>
              <button onClick={() => setShowRight(false)} className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text-secondary">
                <ChevronRight size={13} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-3">
              {tracker ? (
                <div className="space-y-2">
                  {tracker.required.map((type) => {
                    const status = tracker.deliverables[type];
                    const isDone = status === 'produced' || status === 'confirmed';
                    const isInProgress = status === 'in_progress';
                    return (
                      <div key={type} className="flex items-center gap-1">
                        <button
                          disabled={!isDone}
                          onClick={async () => {
                            if (!isDone || !id) return;
                            try {
                              const artifacts = await api.listArtifacts(id);
                              const match = artifacts.find((a) => a.artifact_type === type);
                              if (match) setDrawerArtifact(match);
                            } catch { /* ignore */ }
                          }}
                          className={`flex flex-1 items-center gap-2.5 rounded-md p-2.5 text-left transition-colors ${
                            isDone ? 'bg-status-done/5 hover:bg-status-done/10 cursor-pointer'
                            : isInProgress ? 'bg-accent/5 cursor-default'
                            : 'bg-bg-elevated cursor-default'
                          }`}
                        >
                          {isDone ? (
                            <CheckCircle2 size={14} className="flex-shrink-0 text-status-done" />
                          ) : isInProgress ? (
                            <Loader2 size={14} className="flex-shrink-0 animate-spin text-accent" />
                          ) : (
                            <Circle size={14} className="flex-shrink-0 text-text-muted" />
                          )}
                          <div className="min-w-0 flex-1">
                            <span className={`text-[11px] font-medium ${
                              isDone ? 'text-status-done' : isInProgress ? 'text-accent' : 'text-text-secondary'
                            }`}>
                              {DELIVERABLE_LABELS[type] || type}
                            </span>
                            {isDone ? (
                              <p className="text-[9px] text-text-muted">点击预览</p>
                            ) : isInProgress ? (
                              <p className="text-[9px] text-accent/70">生成中...</p>
                            ) : (
                              <p className="text-[9px] text-text-muted">待生成</p>
                            )}
                          </div>
                        </button>
                        {type === 'prototype' && isDone && (
                          <button
                            title="产品预览"
                            onClick={async (e) => {
                              e.stopPropagation();
                              if (!id) return;
                              try {
                                const artifacts = await api.listArtifacts(id);
                                const match = artifacts.find((a) => a.artifact_type === 'prototype');
                                if (match?.content) openPrototypeInNewTab(match.content as Record<string, unknown>);
                              } catch { /* ignore */ }
                            }}
                            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-accent transition-colors hover:bg-accent/10"
                          >
                            <ExternalLink size={13} />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[11px] text-text-muted">暂无交付物信息</p>
              )}
              {tracker && tracker.is_complete && (
                <div className="mt-4 rounded-md border border-status-done/30 bg-status-done/5 p-3 text-center">
                  <CheckCircle2 size={20} className="mx-auto mb-1 text-status-done" />
                  <p className="text-xs font-medium text-status-done">全部交付物已完成</p>
                </div>
              )}
            </div>

            {relatedExps.length > 0 && (
              <div className="border-t border-border px-3 pt-2 pb-3">
                <div className="mb-1 flex items-center gap-1 px-1">
                  <Lightbulb size={10} className="text-accent" />
                  <span className="text-[9px] font-medium text-text-tertiary">相关经验</span>
                </div>
                {relatedExps.slice(0, 2).map((exp) => (
                  <button key={exp.id} onClick={() => setSelectedExp(exp)} className="mb-1 w-full rounded px-1.5 py-1 text-left text-[10px] text-text-secondary transition-colors hover:bg-bg-elevated">
                    <span className="line-clamp-1">{exp.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex w-10 flex-shrink-0 flex-col items-center border-l border-border bg-bg-sidebar py-3">
            <button onClick={() => setShowRight(true)} title="展开交付物面板" className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-accent">
              <FileText size={14} />
            </button>
          </div>
        ))}
      </div>

      <ExperienceDetailModal experience={selectedExp} onClose={() => setSelectedExp(null)} />
      <DeliverableDrawer
        open={!!drawerArtifact}
        onClose={() => setDrawerArtifact(null)}
        content={drawerArtifact ? { type: 'artifact', data: drawerArtifact } : null}
      />
    </>
  );
}

function openPrototypeInNewTab(content: Record<string, unknown>) {
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

  const blobUrls = pages.map(p => {
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
  window.open(URL.createObjectURL(shellBlob), '_blank');
}
