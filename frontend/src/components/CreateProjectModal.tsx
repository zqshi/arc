import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { ProjectType, WorkspaceType, BuildTarget, BuildTargetReadiness } from '../types/api';
import { InfoStep } from './create-project-modal-parts';
import { WorkspaceStep, ModalFooter } from './create-project-modal-workspace-parts';

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
  // v6.19 T11: 构建目标就绪状态 (未就绪目标灰显 + 标注原因, 避免选了必失败)
  const [readiness, setReadiness] = useState<Record<string, BuildTargetReadiness>>({});

  useEffect(() => {
    let cancelled = false;
    api
      .getBuildTargetReadiness()
      .then((list) => {
        if (cancelled) return;
        const map: Record<string, BuildTargetReadiness> = {};
        for (const item of list) map[item.target] = item;
        setReadiness(map);
      })
      .catch(() => {
        // 就绪查询失败不阻断创建 (视为未知, 不灰显)
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canNext = name.trim().length > 0;
  const canCreate = Boolean(
    workspaceType === 'temporary' ||
    (workspaceType === 'local' && localPath) ||
    (workspaceType === 'github' && repoUrl.trim())
  );

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
            <InfoStep
              name={name}
              desc={desc}
              projectType={projectType}
              buildTarget={buildTarget}
              readiness={readiness}
              canNext={canNext}
              onNameChange={setName}
              onDescChange={setDesc}
              onProjectTypeChange={setProjectType}
              onBuildTargetChange={setBuildTarget}
              onNext={() => setStep('workspace')}
            />
          ) : (
            <WorkspaceStep
              workspaceType={workspaceType}
              localPath={localPath}
              showPicker={showPicker}
              repoUrl={repoUrl}
              githubToken={githubToken}
              onWorkspaceTypeChange={(t, sp) => {
                setWorkspaceType(t);
                setShowPicker(sp);
              }}
              onShowPickerChange={(v) => setShowPicker(v)}
              onLocalPathChange={setLocalPath}
              onRepoUrlChange={setRepoUrl}
              onGithubTokenChange={setGithubToken}
            />
          )}
        </div>

        <ModalFooter
          step={step}
          canNext={canNext}
          canCreate={canCreate}
          creating={creating}
          onBack={() => setStep('info')}
          onClose={onClose}
          onNext={() => setStep('workspace')}
          onCreate={handleCreate}
        />
      </div>
    </div>
  );
}
