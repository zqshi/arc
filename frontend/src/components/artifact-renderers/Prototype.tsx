import { Monitor, Navigation, ExternalLink, Loader2, AlertTriangle, GitBranch } from 'lucide-react';
import { SectionCard, TextBlock } from './shared';

interface Props {
  content: Record<string, unknown>;
}

interface RouteItem {
  path?: string;
  name?: string;
  component?: string;
}

export default function Prototype({ content }: Props) {
  const previewUrl = content.preview_url as string | undefined;
  const buildStatus = content.build_status as string | undefined;
  const routes = (content.routes || []) as RouteItem[];
  const techStack = content.tech_stack as string | undefined;
  const projectDir = content.project_dir as string | undefined;
  const sharedState = (content.shared_state || []) as string[];

  return (
    <div>
      {/* 构建状态 */}
      {buildStatus === 'building' && (
        <SectionCard icon={<Loader2 size={13} className="animate-spin" />} title="构建中...">
          <p className="text-[11px] text-text-muted">正在构建前端工程，请稍候。</p>
        </SectionCard>
      )}

      {buildStatus === 'failed' && (
        <SectionCard icon={<AlertTriangle size={13} className="text-red-400" />} title="构建失败">
          <p className="text-[11px] text-red-300">前端工程构建失败，请检查 AI 对话中的错误输出。</p>
        </SectionCard>
      )}

      {/* 预览 — 加载真实部署的 SPA */}
      {previewUrl && (
        <SectionCard icon={<Monitor size={13} />} title="产品预览">
          <div className="rounded-lg overflow-hidden border border-border/30">
            <iframe
              src={previewUrl}
              className="w-full border-0"
              style={{ height: '600px' }}
              title="原型预览"
            />
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {techStack && (
                <span className="rounded bg-bg-elevated px-2 py-0.5 text-[10px] text-text-muted">
                  {techStack}
                </span>
              )}
              {projectDir && (
                <span className="rounded bg-bg-elevated px-2 py-0.5 text-[10px] text-text-muted font-mono">
                  {projectDir}/
                </span>
              )}
            </div>
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover"
            >
              <ExternalLink size={11} /> 在新窗口打开
            </a>
          </div>
        </SectionCard>
      )}

      {/* 路由表 */}
      {routes.length > 0 && (
        <SectionCard icon={<Navigation size={13} />} title="页面路由">
          <div className="space-y-1">
            {routes.map((route, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-md bg-bg-elevated px-3 py-2"
              >
                <code className="text-[10px] font-mono text-accent min-w-[80px]">
                  {route.path || '/'}
                </code>
                <span className="text-[11px] text-text-primary flex-1">
                  {route.name || '未命名'}
                </span>
                <span className="text-[10px] text-text-muted font-mono truncate max-w-[180px]">
                  {route.component || ''}
                </span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* 全局状态 */}
      {sharedState.length > 0 && (
        <SectionCard icon={<GitBranch size={13} />} title="全局状态">
          <div className="flex flex-wrap gap-1.5">
            {sharedState.map((state, i) => (
              <span
                key={i}
                className="rounded-full bg-bg-elevated border border-border/30 px-2.5 py-0.5 text-[10px] text-text-secondary"
              >
                {state}
              </span>
            ))}
          </div>
        </SectionCard>
      )}

      {/* 无原型时的空状态 */}
      {!previewUrl && buildStatus !== 'building' && buildStatus !== 'failed' && (
        <SectionCard icon={<Monitor size={13} />} title="原型设计">
          <TextBlock>工程尚未构建或部署。AI 将在设计阶段自动创建前端工程并构建部署。</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
