import { CodeBlock, LabeledField, SectionTitle } from './shared';
import { asString } from './utils';

interface Content {
  project_dir?: string;
  tech_stack?: string[];
  framework?: string;
  build_command?: string;
  run_command?: string;
  entry_points?: string[];
  has_backend?: boolean;
  backend_type?: string;
}

/**
 * v5.5.0: APP_CODE artifact 渲染器。
 * Agent 产出的机器可解析代码工程元数据 — UI 只读。
 */
export default function AppCode({ content }: { content: Content }) {
  return (
    <div className="space-y-4">
      <SectionTitle>工程元数据</SectionTitle>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <LabeledField label="代码目录" value={content.project_dir} mono />
        <LabeledField label="框架" value={content.framework} />
        <LabeledField label="构建命令" value={content.build_command} mono />
        <LabeledField label="运行命令" value={content.run_command} mono />
        <LabeledField
          label="后端类型"
          value={
            content.has_backend
              ? (content.backend_type ?? '(未指定)')
              : '无后端 (纯前端)'
          }
        />
      </div>

      {content.tech_stack && content.tech_stack.length > 0 && (
        <div>
          <SectionTitle>技术栈</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {content.tech_stack.map((tech, i) => (
              <span
                key={`${tech}-${i}`}
                className="rounded bg-bg-elevated px-2 py-0.5 text-[11px] text-text-secondary"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {content.entry_points && content.entry_points.length > 0 && (
        <div>
          <SectionTitle>入口文件</SectionTitle>
          <ul className="space-y-1 text-[11px] text-text-secondary">
            {content.entry_points.map((ep, i) => (
              <li key={`${ep}-${i}`} className="font-mono">{ep}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-[11px] text-text-muted">原始 JSON</summary>
        <CodeBlock>{asString(content)}</CodeBlock>
      </details>
    </div>
  );
}

