import { useEffect, useId, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#6C63FF',
    primaryTextColor: '#E8E6E3',
    primaryBorderColor: '#4A4458',
    lineColor: '#6C63FF',
    secondaryColor: '#2A2A3E',
    tertiaryColor: '#1E1E2E',
    fontFamily: 'system-ui, sans-serif',
    fontSize: '13px',
  },
  flowchart: { curve: 'basis', padding: 16 },
});

let counter = 0;

interface Props {
  code: string;
}

export default function MermaidDiagram({ code }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const reactId = useId();
  const seqRef = useRef(++counter);
  const renderKey = `mmd-${reactId.replace(/:/g, '')}-${seqRef.current}`;

  useEffect(() => {
    if (!containerRef.current || !code.trim()) return;

    let cancelled = false;
    const elemId = `${renderKey}-${Date.now()}`;

    async function render() {
      try {
        const { svg } = await mermaid.render(elemId, code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Mermaid 渲染失败');
        }
      }
    }

    render();
    return () => {
      cancelled = true;
      document.getElementById('d' + elemId)?.remove();
    };
  }, [code, renderKey]);

  if (error) {
    return (
      <div className="rounded-md border border-status-error/20 bg-status-error/5 p-3">
        <p className="mb-2 text-xs text-status-error">流程图渲染失败</p>
        <pre className="whitespace-pre-wrap font-mono text-[11px] text-text-muted">{code}</pre>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex items-center justify-center overflow-x-auto rounded-md bg-bg-card p-4 [&_svg]:max-w-full"
    />
  );
}
