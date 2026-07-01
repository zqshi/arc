import { FolderOpen, GitBranch, Zap, Monitor, Globe, Smartphone, FileCode, AppWindow, Apple, Tablet } from 'lucide-react';
import type { ProjectType, WorkspaceType, BuildTarget, BuildTargetReadiness } from '../types/api';

export const WORKSPACE_OPTIONS: Array<{
  type: WorkspaceType;
  icon: typeof Zap;
  title: string;
  desc: string;
}> = [
  { type: 'temporary', icon: Zap, title: '快速开始', desc: '自动创建临时工作区，随时可迁移到正式目录' },
  { type: 'local', icon: FolderOpen, title: '关联本地目录', desc: '选择已有的项目文件夹' },
  { type: 'github', icon: GitBranch, title: '从 GitHub 克隆', desc: '输入仓库地址，自动克隆到本地' },
];

// v6.0: 项目类型选择器 (T6 波次1 构建链路就绪后放开 binary_app)
export const PROJECT_TYPE_OPTIONS: Array<{
  type: ProjectType;
  icon: typeof Globe;
  title: string;
  desc: string;
  requiresDocker?: boolean;
}> = [
  { type: 'static_site', icon: Globe, title: '静态站点', desc: '官网 / SPA / 落地页，构建为可托管静态资源' },
  { type: 'binary_app', icon: Monitor, title: '原生客户端', desc: '桌面 / Web / Android 原生客户端，容器化构建', requiresDocker: true },
];

// v6.19: BINARY_APP 构建目标 (linux/web/apk=DOCKER 容器构建; windows/ios/鸿蒙=CI 编排原生构建)
export const BUILD_TARGET_OPTIONS: Array<{
  target: BuildTarget;
  icon: typeof Globe;
  title: string;
  desc: string;
}> = [
  { target: 'tauri_linux', icon: Monitor, title: 'Linux 桌面', desc: 'Tauri 打包 deb/AppImage（默认）' },
  { target: 'web', icon: FileCode, title: 'Web 资源', desc: 'npm run build 产 dist，不打包原生客户端' },
  { target: 'capacitor_apk', icon: Smartphone, title: 'Android APK', desc: 'Capacitor 构建 android apk' },
  { target: 'tauri_windows', icon: AppWindow, title: 'Windows', desc: 'CI 构建 .msi/.exe' },
  { target: 'capacitor_ios', icon: Apple, title: 'iOS', desc: 'CI 构建 .ipa' },
  { target: 'harmony_hap', icon: Tablet, title: '鸿蒙', desc: 'CI 构建 .hap' },
];

/** 项目类型选择器 */
export function ProjectTypeSelector({
  value,
  onChange,
}: {
  value: ProjectType;
  onChange: (t: ProjectType) => void;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">项目类型</label>
      <div className="grid grid-cols-2 gap-2">
        {PROJECT_TYPE_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const active = value === opt.type;
          return (
            <button
              key={opt.type}
              type="button"
              onClick={() => onChange(opt.type)}
              className={`flex flex-col items-start gap-1 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                active
                  ? 'border-accent bg-accent/5'
                  : 'border-border hover:border-border-active hover:bg-bg-elevated/50'
              }`}
            >
              <div className="flex items-center gap-1.5">
                <Icon size={13} className={active ? 'text-accent' : 'text-text-muted'} />
                <span className={`text-xs font-medium ${active ? 'text-accent' : 'text-text-primary'}`}>
                  {opt.title}
                </span>
              </div>
              <span className="text-[10px] leading-tight text-text-muted">{opt.desc}</span>
              {opt.requiresDocker && (
                <span className="text-[10px] text-status-warning">构建需 Docker</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** 构建目标选择器 (binary_app 专属) */
export function BuildTargetSelector({
  value,
  readiness,
  onChange,
}: {
  value: BuildTarget;
  readiness: Record<string, BuildTargetReadiness>;
  onChange: (t: BuildTarget) => void;
}) {
  return (
    <div className="mt-3">
      <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
        构建目标 <span className="text-text-muted">（决定容器内构建形态）</span>
      </label>
      <div className="grid grid-cols-3 gap-2">
        {BUILD_TARGET_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const active = value === opt.target;
          const r = readiness[opt.target];
          const blocked = Boolean(r && !r.ready);
          return (
            <button
              key={opt.target}
              type="button"
              onClick={() => !blocked && onChange(opt.target)}
              disabled={blocked}
              className={`flex flex-col items-start gap-1 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                active
                  ? 'border-accent bg-accent/5'
                  : blocked
                    ? 'cursor-not-allowed border-border opacity-50'
                    : 'border-border hover:border-border-active hover:bg-bg-elevated/50'
              }`}
            >
              <div className="flex items-center gap-1">
                <Icon size={12} className={active ? 'text-accent' : 'text-text-muted'} />
                <span className={`text-[11px] font-medium ${active ? 'text-accent' : 'text-text-primary'}`}>
                  {opt.title}
                </span>
              </div>
              <span className="text-[10px] leading-tight text-text-muted">{opt.desc}</span>
              {blocked && r && (
                <span className="text-[10px] leading-tight text-status-warning">{r.reason}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Step1: 名称 + 描述 + 项目类型 (+ 构建目标) */
export function InfoStep({
  name,
  desc,
  projectType,
  buildTarget,
  readiness,
  canNext,
  onNameChange,
  onDescChange,
  onProjectTypeChange,
  onBuildTargetChange,
  onNext,
}: {
  name: string;
  desc: string;
  projectType: ProjectType;
  buildTarget: BuildTarget;
  readiness: Record<string, BuildTargetReadiness>;
  canNext: boolean;
  onNameChange: (v: string) => void;
  onDescChange: (v: string) => void;
  onProjectTypeChange: (t: ProjectType) => void;
  onBuildTargetChange: (t: BuildTarget) => void;
  onNext: () => void;
}) {
  return (
    <>
      <div className="mb-4">
        <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
          项目名称 <span className="text-status-error">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="例如：Arc 工作台"
          className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter' && canNext) onNext();
          }}
        />
      </div>
      <div>
        <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">描述</label>
        <textarea
          value={desc}
          onChange={(e) => onDescChange(e.target.value)}
          placeholder="项目的简要描述"
          rows={2}
          className="w-full resize-none rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
        />
      </div>
      <ProjectTypeSelector value={projectType} onChange={onProjectTypeChange} />
      {projectType === 'binary_app' && (
        <BuildTargetSelector value={buildTarget} readiness={readiness} onChange={onBuildTargetChange} />
      )}
    </>
  );
}
