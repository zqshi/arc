/**
 * HtmlApplyButton — 检测消息内容中的 HTML 代码块，提供「应用到原型」按钮。
 *
 * 在 AI 消息渲染后显示。点击后通过回调将 HTML 传递到原型 iframe。
 */

import { useState } from 'react';
import { Play, Check } from 'lucide-react';

interface Props {
  content: string;
  onApply?: (html: string) => void;
}

// 匹配 ```html ... ``` 代码块
const HTML_BLOCK_RE = /```html\s*\n([\s\S]*?)```/g;

export function extractHtmlBlocks(content: string): string[] {
  const blocks: string[] = [];
  let match: RegExpExecArray | null;
  const re = new RegExp(HTML_BLOCK_RE.source, 'g');
  while ((match = re.exec(content)) !== null) {
    const html = match[1].trim();
    if (html) blocks.push(html);
  }
  return blocks;
}

export default function HtmlApplyButton({ content, onApply }: Props) {
  const [applied, setApplied] = useState(false);
  const blocks = extractHtmlBlocks(content);

  if (blocks.length === 0 || !onApply) return null;

  const handleApply = () => {
    // Apply 最后一个 HTML 代码块（通常是修改后的最终版本）
    onApply(blocks[blocks.length - 1]);
    setApplied(true);
    setTimeout(() => setApplied(false), 3000);
  };

  return (
    <button
      onClick={handleApply}
      disabled={applied}
      className={`mt-2 flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium transition-colors ${
        applied
          ? 'border-status-done/40 bg-status-done/10 text-status-done cursor-default'
          : 'border-accent/40 bg-accent/10 text-accent hover:bg-accent/20'
      }`}
    >
      {applied ? <><Check size={11} /> 已应用</> : <><Play size={11} /> 应用到原型</>}
    </button>
  );
}
