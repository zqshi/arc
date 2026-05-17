import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

const components: Components = {
  pre({ children }) {
    return (
      <pre className="my-1.5 overflow-x-auto rounded-md bg-[#1e1e2e] p-3 text-[11px] leading-relaxed">
        {children}
      </pre>
    );
  },
  code({ children, className }) {
    const isBlock = className?.startsWith('language-');
    if (isBlock) {
      return <code className="text-[#cdd6f4]">{children}</code>;
    }
    return (
      <code className="rounded bg-bg-elevated px-1 py-0.5 text-[11px] text-accent">
        {children}
      </code>
    );
  },
  ul({ children }) {
    return <ul className="my-1 list-disc space-y-0.5 pl-4">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="my-1 list-decimal space-y-0.5 pl-4">{children}</ol>;
  },
  li({ children }) {
    return <li className="text-xs leading-relaxed">{children}</li>;
  },
  p({ children }) {
    return <p className="my-1 first:mt-0 last:mb-0">{children}</p>;
  },
  strong({ children }) {
    return <strong className="font-semibold text-text-primary">{children}</strong>;
  },
  h3({ children }) {
    return <h3 className="mt-2 mb-1 text-xs font-semibold text-text-primary">{children}</h3>;
  },
  h4({ children }) {
    return <h4 className="mt-1.5 mb-0.5 text-[11px] font-semibold text-text-primary">{children}</h4>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="my-1 border-l-2 border-accent/30 pl-2 text-text-muted">
        {children}
      </blockquote>
    );
  },
  table({ children }) {
    return (
      <div className="my-1.5 overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-border bg-bg-elevated px-2 py-1 text-left font-medium text-text-primary">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border border-border px-2 py-1">{children}</td>;
  },
};

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </Markdown>
  );
}
