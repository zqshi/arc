import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

const components: Components = {
  pre({ children }) {
    return (
      <pre className="my-3 overflow-x-auto rounded-lg bg-[#1e1e2e] p-4 text-xs leading-relaxed">
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
      <code className="rounded bg-bg-elevated px-1.5 py-0.5 text-[11px] font-medium text-accent">
        {children}
      </code>
    );
  },
  ul({ children }) {
    return <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>;
  },
  li({ children }) {
    return <li className="text-[13px] leading-relaxed text-text-secondary">{children}</li>;
  },
  p({ children }) {
    return <p className="my-2 text-[13px] leading-relaxed text-text-secondary first:mt-0 last:mb-0">{children}</p>;
  },
  strong({ children }) {
    return <strong className="font-semibold text-text-primary">{children}</strong>;
  },
  h1({ children }) {
    return <h1 className="mt-6 mb-3 text-lg font-bold text-text-primary first:mt-0">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="mt-5 mb-2.5 text-base font-bold text-text-primary first:mt-0">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="mt-4 mb-2 text-sm font-semibold text-text-primary first:mt-0">{children}</h3>;
  },
  h4({ children }) {
    return <h4 className="mt-3 mb-1.5 text-[13px] font-semibold text-text-primary first:mt-0">{children}</h4>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="my-3 rounded-r-md border-l-3 border-accent/40 bg-accent/5 py-2 pl-4 pr-3 text-[13px] text-text-secondary">
        {children}
      </blockquote>
    );
  },
  table({ children }) {
    return (
      <div className="my-3 overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-[12px]">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border-b border-border bg-bg-elevated px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-tertiary">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border-b border-border/50 px-3 py-2 text-[12px] text-text-secondary">{children}</td>;
  },
  hr() {
    return <hr className="my-4 border-border/50" />;
  },
};

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </Markdown>
  );
}
