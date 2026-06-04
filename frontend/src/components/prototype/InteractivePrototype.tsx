/**
 * InteractivePrototype — 支持元素选中 + AI 对话交互的原型预览器。
 *
 * 功能：
 * - Inspect 模式开关（选中元素 → 高亮 → 上报信息）
 * - 选中元素面板展示属性
 * - 自然语言修改入口（集成到对话输入）
 * - Undo 支持
 */

import { useState, useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react';
import { MousePointer2, Undo2, Code, X } from 'lucide-react';
import { injectInspector, type SelectedElementInfo } from './inspector';

interface Props {
  html: string;
  pageName: string;
  description?: string;
  onElementSelected?: (info: SelectedElementInfo) => void;
  onRequestModify?: (info: SelectedElementInfo, instruction: string) => void;
}

export interface InteractivePrototypeHandle {
  applyHtml: (html: string) => void;
  undo: () => void;
}

const TAILWIND_CDN = 'https://cdn.tailwindcss.com';

function buildSrcDoc(html: string): string {
  const inspectedHtml = injectInspector(html);
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="${TAILWIND_CDN}"></script>
<style>
  body { margin: 0; padding: 16px; background: #1E1E2E; color: #E8E6E3; font-family: system-ui, sans-serif; }
  * { box-sizing: border-box; }
</style>
</head>
<body>${inspectedHtml}</body>
</html>`;
}

export default forwardRef<InteractivePrototypeHandle, Props>(function InteractivePrototype({ html, pageName, description, onElementSelected, onRequestModify }, ref) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(350);
  const [inspectMode, setInspectMode] = useState(false);
  const [selectedElement, setSelectedElement] = useState<SelectedElementInfo | null>(null);
  const [modifyInput, setModifyInput] = useState('');
  const [showCode, setShowCode] = useState(false);

  // 监听 iframe postMessage
  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.type === 'element_selected') {
        const info = e.data.data as SelectedElementInfo;
        setSelectedElement(info);
        onElementSelected?.(info);
      }
      if (e.data.type === 'apply_done') {
        setSelectedElement(null);
        setModifyInput('');
      }
    }
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onElementSelected]);

  // iframe 高度自适应
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    function adjustHeight() {
      try {
        const doc = iframe!.contentDocument;
        if (doc?.body) {
          setHeight(Math.min(Math.max(doc.body.scrollHeight + 32, 200), 800));
        }
      } catch { /* */ }
    }
    iframe.addEventListener('load', adjustHeight);
    return () => iframe.removeEventListener('load', adjustHeight);
  }, [html]);

  // Expose applyHtml/undo via ref
  useImperativeHandle(ref, () => ({
    applyHtml: (newHtml: string) => {
      iframeRef.current?.contentWindow?.postMessage({ type: 'apply_html', html: newHtml }, '*');
    },
    undo: () => {
      iframeRef.current?.contentWindow?.postMessage({ type: 'undo' }, '*');
    },
  }));

  // 切换 inspect 模式
  const toggleInspect = useCallback(() => {
    const next = !inspectMode;
    setInspectMode(next);
    iframeRef.current?.contentWindow?.postMessage({ type: 'set_inspect_mode', enabled: next }, '*');
    if (!next) {
      setSelectedElement(null);
      iframeRef.current?.contentWindow?.postMessage({ type: 'deselect' }, '*');
    }
  }, [inspectMode]);

  // Undo
  const handleUndo = useCallback(() => {
    iframeRef.current?.contentWindow?.postMessage({ type: 'undo' }, '*');
    setSelectedElement(null);
  }, []);

  // 提交修改
  const handleSubmitModify = () => {
    if (!selectedElement || !modifyInput.trim()) return;
    onRequestModify?.(selectedElement, modifyInput.trim());
    setModifyInput('');
  };

  return (
    <div className="rounded-lg border border-border/50 bg-bg-card overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border/30 px-3 py-2">
        <div className="min-w-0">
          <h5 className="text-xs font-medium text-text-primary">{pageName}</h5>
          {description && <p className="mt-0.5 text-[10px] text-text-muted truncate">{description}</p>}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={toggleInspect}
            className={`flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors ${
              inspectMode
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-text-muted hover:text-text-secondary hover:border-border-active'
            }`}
            title="选中元素模式"
          >
            <MousePointer2 size={11} /> {inspectMode ? '选中模式' : '选择元素'}
          </button>
          <button
            onClick={handleUndo}
            className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-muted hover:text-text-secondary"
            title="撤销修改"
          >
            <Undo2 size={11} />
          </button>
          <button
            onClick={() => setShowCode(!showCode)}
            className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-muted hover:text-text-secondary"
          >
            <Code size={11} /> {showCode ? '隐藏' : '代码'}
          </button>
        </div>
      </div>

      {/* iframe */}
      <iframe
        ref={iframeRef}
        srcDoc={buildSrcDoc(html)}
        sandbox="allow-scripts"
        className="w-full border-0"
        style={{ height: `${height}px` }}
        title={`原型 - ${pageName}`}
      />

      {/* Selected element panel */}
      {selectedElement && (
        <div className="border-t border-border/30 bg-bg-elevated px-3 py-2.5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-medium text-text-tertiary uppercase tracking-wide">已选中元素</span>
            <button onClick={() => {
              setSelectedElement(null);
              iframeRef.current?.contentWindow?.postMessage({ type: 'deselect' }, '*');
            }} className="text-text-muted hover:text-text-secondary">
              <X size={12} />
            </button>
          </div>
          <div className="flex items-center gap-2 mb-2">
            <code className="rounded bg-bg-card px-1.5 py-0.5 text-[10px] font-mono text-accent">{selectedElement.tagName}</code>
            <span className="truncate text-[11px] text-text-secondary">{selectedElement.text.slice(0, 60)}</span>
          </div>
          {/* Modify input */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={modifyInput}
              onChange={(e) => setModifyInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitModify(); }}
              placeholder="描述修改意图…（如：改大字号、换蓝色背景）"
              className="h-7 flex-1 rounded-md border border-border bg-bg-input px-2.5 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
            <button
              onClick={handleSubmitModify}
              disabled={!modifyInput.trim()}
              className="h-7 rounded-md bg-accent px-3 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-40"
            >
              修改
            </button>
          </div>
        </div>
      )}

      {/* Code panel */}
      {showCode && (
        <div className="border-t border-border/30 bg-[#1a1b26] p-3 max-h-48 overflow-auto">
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[#9ece6a]">
            {html}
          </pre>
        </div>
      )}
    </div>
  );
});
