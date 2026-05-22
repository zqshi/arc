import { useEffect, useRef, useState } from 'react';

interface Props {
  pageName: string;
  description?: string;
  html: string;
}

const TAILWIND_CDN = 'https://cdn.tailwindcss.com';

function buildSrcDoc(html: string): string {
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
<body>${html}</body>
</html>`;
}

export default function WireframePreview({ pageName, description, html }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(300);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    function adjustHeight() {
      try {
        const doc = iframe!.contentDocument;
        if (doc?.body) {
          const h = doc.body.scrollHeight + 32;
          setHeight(Math.min(Math.max(h, 200), 800));
        }
      } catch {
        // cross-origin — keep default
      }
    }

    iframe.addEventListener('load', adjustHeight);
    return () => iframe.removeEventListener('load', adjustHeight);
  }, [html]);

  return (
    <div className="rounded-lg border border-border/50 bg-bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/30 px-3 py-2">
        <div>
          <h5 className="text-xs font-medium text-text-primary">{pageName}</h5>
          {description && (
            <p className="mt-0.5 text-[10px] text-text-muted">{description}</p>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="rounded px-2 py-0.5 text-[10px] text-text-tertiary hover:bg-bg-elevated hover:text-text-secondary"
        >
          {expanded ? '收起代码' : '查看代码'}
        </button>
      </div>

      <iframe
        ref={iframeRef}
        srcDoc={buildSrcDoc(html)}
        sandbox="allow-scripts"
        className="w-full border-0"
        style={{ height: `${height}px` }}
        title={`线框图 - ${pageName}`}
      />

      {expanded && (
        <div className="border-t border-border/30 bg-[#1a1b26] p-3">
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[#9ece6a]">
            {html}
          </pre>
        </div>
      )}
    </div>
  );
}
