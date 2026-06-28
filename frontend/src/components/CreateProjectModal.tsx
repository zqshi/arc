import { useState } from 'react';
import { FolderOpen, GitBranch, Zap, ChevronRight, ChevronLeft, Loader2, Monitor, Globe, Smartphone, FileCode } from 'lucide-react';
import FolderPicker from './FolderPicker';
import type { ProjectType, WorkspaceType, BuildTarget } from '../types/api';

type Step = 'info' | 'workspace';

interface Props {
  onClose: () => void;
  onCreate: (data: {
    name: string;
    description: string;
    project_type: ProjectType;
    workspace_type: WorkspaceType;
    local_path?: string;
    repo_url?: string;
    github_token?: string;
  }) => Promise<void>;
}

const WORKSPACE_OPTIONS: Array<{
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
const PROJECT_TYPE_OPTIONS: Array<{
  type: ProjectType;
  icon: typeof Globe;
  title: string;
  desc: string;
  requiresDocker?: boolean;
}> = [
  { type: 'static_site', icon: Globe, title: '静态站点', desc: '官网 / SPA / 落地页，构建为可托管静态资源' },
  { type: 'binary_app', icon: Monitor, title: '原生客户端', desc: '桌面 / Web / Android 原生客户端，容器化构建', requiresDocker: true },
];

// v6.12: BINARY_APP 构建目标选择 (决定容器内构建形态 + 镜像)
const BUILD_TARGET_OPTIONS: Array<{
  target: BuildTarget;
  icon: typeof Globe;
  title: string;
  desc: string;
}> = [
  { target: 'tauri_linux', icon: Monitor, title: 'Linux 桌面', desc: 'Tauri 打包 deb/AppImage（默认）' },
  { target: 'web', icon: FileCode, title: 'Web 资源', desc: 'npm run build 产 dist，不打包原生客户端' },
  { target: 'capacitor_apk', icon: Smartphone, title: 'Android APK', desc: 'Capacitor 构建 android apk' },
];

export default function CreateProjectModal({ onClose, onCreate }: Props) {
  const [step, setStep] = useState<Step>('info');
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [projectType, setProjectType] = useState<ProjectType>('static_site');
  const [buildTarget, setBuildTarget] = useState<BuildTarget>('tauri_linux');
  const [workspaceType, setWorkspaceType] = useState<WorkspaceType>('temporary');
  const [localPath, setLocalPath] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [showPicker, setShowPicker] = useState(false);
  const [creating, setCreating] = useState(false);

  const canNext = name.trim().length > 0;
  const canCreate =
    workspaceType === 'temporary' ||
    (workspaceType === 'local' && localPath) ||
    (workspaceType === 'github' && repoUrl.trim());

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    try {
      await onCreate({
        name: name.trim(),
        description: desc.trim(),
        project_type: projectType,
        ...(projectType === 'binary_app' ? { build_target: buildTarget } : {}),
        workspace_type: workspaceType,
        ...(workspaceType === 'local' && localPath ? { local_path: localPath } : {}),
        ...(workspaceType === 'github' && repoUrl ? { repo_url: repoUrl.trim(), github_token: githubToken.trim() || undefined } : {}),
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-[520px] animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="font-heading text-sm font-semibold text-text-primary">
            {step === 'info' ? '新建项目' : '选择工作区'}
          </h2>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className={`h-1.5 w-4 rounded-full transition-colors ${step === 'info' ? 'bg-accent' : 'bg-accent/30'}`} />
              <span className={`h-1.5 w-4 rounded-full transition-colors ${step === 'workspace' ? 'bg-accent' : 'bg-accent/30'}`} />
            </span>
            <button
              onClick={onClose}
              className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary"
            >
              ×
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          {step === 'info' ? (
            // ──── Step 1: Name + Description ────
            <>
              <div className="mb-4">
                <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
                  项目名称 <span className="text-status-error">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：Arc 工作台"
                  className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && canNext) setStep('workspace');
                  }}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">描述</label>
                <textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="项目的简要描述"
                  rows={2}
                  className="w-full resize-none rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">项目类型</label>
                <div className="grid grid-cols-2 gap-2">
                  {PROJECT_TYPE_OPTIONS.map((opt) => {
                    const Icon = opt.icon;
                    const active = projectType === opt.type;
                    return (
                      <button
                        key={opt.type}
                        type="button"
                        onClick={() => setProjectType(opt.type)}
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
              {projectType === 'binary_app' && (
                <div className="mt-3">
                  <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
                    构建目标 <span className="text-text-muted">（决定容器内构建形态）</span>
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {BUILD_TARGET_OPTIONS.map((opt) => {
                      const Icon = opt.icon;
                      const active = buildTarget === opt.target;
                      return (
                        <button
                          key={opt.target}
                          type="button"
                          onClick={() => setBuildTarget(opt.target)}
                          className={`flex flex-col items-start gap-1 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                            active
                              ? 'border-accent bg-accent/5'
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
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            // ──── Step 2: Workspace Selection ────
            <>
              <div className="space-y-2">
                {WORKSPACE_OPTIONS.map((opt) => {
                  const Icon = opt.icon;
                  const active = workspaceType === opt.type;
                  return (
                    <button
                      key={opt.type}
                      onClick={() => {
                        setWorkspaceType(opt.type);
                        if (opt.type === 'local') setShowPicker(true);
                        else setShowPicker(false);
                      }}
                      className={`flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
                        active
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-border-active hover:bg-bg-elevated/50'
                      }`}
                    >
                      <Icon size={16} className={`mt-0.5 flex-shrink-0 ${active ? 'text-accent' : 'text-text-muted'}`} />
                      <div className="min-w-0">
                        <div className={`text-xs font-medium ${active ? 'text-accent' : 'text-text-primary'}`}>
                          {opt.title}
                        </div>
                        <div className="text-[11px] text-text-muted">{opt.desc}</div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Workspace-specific inputs */}
              {workspaceType === 'local' && (
                <div className="mt-3">
                  {showPicker ? (
                    <div className="overflow-hidden rounded-lg border border-border">
                      <FolderPicker
                        open={showPicker}
                        onSelect={(path) => {
                          setLocalPath(path);
                          setShowPicker(false);
                        }}
                        onClose={() => setShowPicker(false)}
                      />
                    </div>
                  ) : localPath ? (
                    <div className="flex items-center gap-2 rounded-md bg-bg-elevated px-3 py-2">
                      <FolderOpen size={12} className="flex-shrink-0 text-accent" />
                      <span className="truncate text-xs text-text-primary">{localPath}</span>
                      <button
                        onClick={() => setShowPicker(true)}
                        className="ml-auto flex-shrink-0 text-[10px] text-accent hover:underline"
                      >
                        更换
                      </button>
                    </div>
                  ) : null}
                </div>
              )}

              {workspaceType === 'github' && (
                <div className="mt-3 space-y-2">
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/owner/repo"
                    className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                  />
                  <input
                    type="password"
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    placeholder="Personal Access Token（可选，私有仓库必填）"
                    className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                  />
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <div>
            {step === 'workspace' && (
              <button
                onClick={() => setStep('info')}
                className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
              >
                <ChevronLeft size={12} /> 上一步
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
            >
              取消
            </button>
            {step === 'info' ? (
              <button
                onClick={() => setStep('workspace')}
                disabled={!canNext}
                className="flex items-center gap-1 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
              >
                下一步 <ChevronRight size={12} />
              </button>
            ) : (
              <button
                onClick={handleCreate}
                disabled={!canCreate || creating}
                className="flex items-center gap-1 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
              >
                {creating ? <Loader2 size={12} className="animate-spin" /> : null}
                创建项目
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
