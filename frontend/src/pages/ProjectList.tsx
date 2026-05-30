import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FolderOpen, Archive, Trash2, RotateCw } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/Toast';
import ActionMenu from '../components/ActionMenu';
import { ProjectListSkeleton } from '../components/Skeleton';
import type { ActionMenuItem } from '../components/ActionMenu';
import type { Project } from '../types/api';

export default function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await api.listProjects(showArchived);
      setProjects(data);
    } catch (err) {
      const msg = err instanceof ApiError ? `${err.status}: ${err.detail}` : String(err);
      setFetchError(msg);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [showArchived]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const project = await api.createProject({
        name: newName.trim(),
        description: newDesc.trim(),
      });
      setShowCreate(false);
      setNewName('');
      setNewDesc('');
      navigate(`/project/${project.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) return;
      toast('创建失败，请检查后端服务是否启动', 'error');
    }
  };

  const handleArchive = async (id: string) => {
    try {
      await api.archiveProject(id);
      fetchProjects();
      toast('项目已归档', 'success');
    } catch {
      toast('归档失败', 'error');
    }
  };

  const handleActivate = async (id: string) => {
    try {
      await api.activateProject(id);
      fetchProjects();
      toast('项目已恢复', 'success');
    } catch {
      toast('恢复失败', 'error');
    }
  };

  const handleDelete = async (project: Project) => {
    if (!window.confirm(`确定删除项目「${project.name}」？删除后可在管理后台恢复。`)) return;
    try {
      await api.deleteProject(project.id);
      fetchProjects();
      toast('项目已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  const getProjectActions = (project: Project): ActionMenuItem[] => {
    const items: ActionMenuItem[] = [];
    if (project.status === 'archived') {
      items.push({ label: '恢复', icon: <RotateCw size={12} />, onClick: () => handleActivate(project.id) });
    } else {
      items.push({ label: '归档', icon: <Archive size={12} />, onClick: () => handleArchive(project.id) });
    }
    items.push({ label: '删除', icon: <Trash2 size={12} />, danger: true, onClick: () => handleDelete(project) });
    return items;
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-lg font-semibold text-text-primary">项目</h1>
          <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] font-medium text-accent">
            {projects.length}
          </span>
          <button
            onClick={() => setShowArchived(!showArchived)}
            className={`ml-3 flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors ${
              showArchived
                ? 'border-accent/30 bg-accent/8 text-accent'
                : 'border-border text-text-muted hover:border-text-muted hover:text-text-secondary'
            }`}
          >
            <Archive size={11} />
            {showArchived ? '隐藏已归档' : '显示已归档'}
          </button>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex h-8 items-center gap-1 rounded-md bg-accent px-3 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
        >
          <Plus size={14} />
          新建项目
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading ? (
          <ProjectListSkeleton />
        ) : fetchError ? (
          <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-status-error/10 text-status-error">!</div>
            <p className="text-sm font-medium text-text-primary">加载失败</p>
            <p className="mt-1.5 max-w-sm text-xs text-status-error">{fetchError}</p>
            <button
              onClick={fetchProjects}
              className="mt-5 rounded-md bg-accent px-5 py-2 text-xs font-medium text-white hover:bg-accent-hover"
            >
              重试
            </button>
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
            <FolderOpen size={44} className="mb-4 text-text-muted" strokeWidth={1.2} />
            <p className="text-sm text-text-secondary">还没有项目</p>
            <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-text-muted">
              创建项目后，可以规划版本、录入需求、启动AI全链路交付Pipeline
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-5 rounded-md bg-accent px-5 py-2 text-xs font-medium text-white hover:bg-accent-hover"
            >
              创建项目
            </button>
          </div>
        ) : (
          <div className="animate-fade-in grid auto-rows-fr grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => navigate(`/project/${project.id}`)}
                className={`group flex cursor-pointer flex-col rounded-lg border bg-bg-card p-5 transition-all hover:bg-bg-elevated ${
                  project.status === 'archived'
                    ? 'border-border/60 opacity-60 hover:opacity-80'
                    : 'border-border hover:border-accent/30'
                }`}
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-[11px] font-bold ${
                      project.status === 'archived'
                        ? 'bg-text-muted/10 text-text-muted'
                        : 'bg-accent/12 text-accent'
                    }`}>
                      {project.name.slice(0, 1).toUpperCase()}
                    </div>
                    <h3 className="truncate text-sm font-semibold text-text-primary">{project.name}</h3>
                  </div>
                  <ActionMenu items={getProjectActions(project)} />
                </div>
                <p className="mb-auto line-clamp-2 text-xs leading-relaxed text-text-secondary">
                  {project.description || '暂无描述'}
                </p>
                <div className="mt-3 flex items-center gap-2 border-t border-border/40 pt-3">
                  {project.tech_stack ? (
                    <span className="truncate rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
                      {project.tech_stack}
                    </span>
                  ) : (
                    <span className="text-[10px] text-text-muted/50">未设置技术栈</span>
                  )}
                  {project.status === 'archived' && (
                    <span className="ml-auto flex items-center gap-1 text-[10px] text-text-muted">
                      <Archive size={10} /> 已归档
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowCreate(false)} />
          <div className="relative mx-4 w-full max-w-[480px] animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h2 className="font-heading text-sm font-semibold text-text-primary">新建项目</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary"
              >
                ×
              </button>
            </div>
            <div className="px-5 py-4">
              <div className="mb-4">
                <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">
                  项目名称 <span className="text-status-error">*</span>
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="例如：Arc 工作台"
                  className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleCreate();
                  }}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-medium text-text-tertiary">描述</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="项目的简要描述"
                  rows={2}
                  className="w-full resize-none rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
