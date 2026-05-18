import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Plus,
  Save,
  GitBranch,
  Play,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  Settings,
  FileText,
  Check,
  Archive,
  ArrowUpRight,
  Trash2,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/Toast';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import ActionMenu from '../components/ActionMenu';
import type { ActionMenuItem } from '../components/ActionMenu';
import type { Project, Version, VersionStatus, VersionType, Todo, TodoStatus, Experience, ExperienceStatus } from '../types/api';
import { STATUS_LABELS, EXPERIENCE_STATUS_LABELS } from '../types/api';
import PhaseProgress from '../components/PhaseProgress';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';

type TabKey = 'todos' | 'experiences' | 'settings';

const TAB_ITEMS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: 'todos', label: '需求', icon: FileText },
  { key: 'experiences', label: '经验', icon: Lightbulb },
  { key: 'settings', label: '设置', icon: Settings },
];

const VERSION_STATUS_STYLE: Record<VersionStatus, { bg: string; label: string }> = {
  planning: { bg: 'bg-status-pending/15 text-status-pending', label: '规划中' },
  active: { bg: 'bg-accent/15 text-accent', label: '进行中' },
  released: { bg: 'bg-status-done/15 text-status-done', label: '已发布' },
};

const statusDotColor: Record<TodoStatus, string> = {
  pending: 'bg-status-pending',
  active: 'bg-accent',
  done: 'bg-status-done',
  error: 'bg-status-error',
};

const statusBadgeBg: Record<TodoStatus, string> = {
  pending: 'bg-status-pending/15 text-status-pending',
  active: 'bg-accent/15 text-accent',
  done: 'bg-status-done/15 text-status-done',
  error: 'bg-status-error/15 text-status-error',
};

const expStatusStyle: Record<ExperienceStatus, { bg: string; dot: string }> = {
  draft: { bg: 'bg-amber-500/15 text-amber-600', dot: 'bg-amber-500' },
  confirmed: { bg: 'bg-status-done/15 text-status-done', dot: 'bg-status-done' },
  archived: { bg: 'bg-text-muted/15 text-text-muted', dot: 'bg-text-muted' },
};

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setProject: setCurrentProject } = useCurrentProject();

  const [project, setProject] = useState<Project | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionTodos, setVersionTodos] = useState<Record<string, Todo[]>>({});
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('todos');

  // Settings form
  const [form, setForm] = useState({ name: '', description: '', tech_stack: '', repo_url: '', conventions: '' });
  const [dirty, setDirty] = useState(false);

  // New version
  const [showNewVersion, setShowNewVersion] = useState(false);
  const [versionName, setVersionName] = useState('');
  const [versionGoal, setVersionGoal] = useState('');
  const [versionType, setVersionType] = useState<VersionType>('minor');

  // Create todo modal
  const [createForVersion, setCreateForVersion] = useState<string | null>(null);

  // Experiences tab
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [expFilter, setExpFilter] = useState<'all' | 'draft' | 'confirmed'>('all');
  const [expLoading, setExpLoading] = useState(false);

  // Insights
  const [insights, setInsights] = useState<Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>>([]);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, v] = await Promise.all([api.getProject(id), api.listVersions(id)]);
      setProject(p);
      setCurrentProject({ id: p.id, name: p.name });
      setVersions(v);
      setForm({
        name: p.name,
        description: p.description,
        tech_stack: p.tech_stack,
        repo_url: p.repo_url,
        conventions: p.conventions,
      });
      setDirty(false);
      const activeIds = new Set(v.filter((ver) => ver.status === 'active').map((ver) => ver.id));
      setExpandedVersions(activeIds.size > 0 ? activeIds : new Set(v.slice(0, 1).map((ver) => ver.id)));
    } catch {
      navigate('/');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  const fetchExperiences = useCallback(async () => {
    if (!id) return;
    setExpLoading(true);
    try {
      const status = expFilter === 'all' ? undefined : expFilter;
      const exps = await api.listProjectExperiences(id, status);
      setExperiences(exps);
    } catch {
      setExperiences([]);
    } finally {
      setExpLoading(false);
    }
  }, [id, expFilter]);

  const fetchInsights = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.getProjectExperienceInsights(id);
      setInsights(data.suggestions);
    } catch {
      setInsights([]);
    }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => () => setCurrentProject(null), [setCurrentProject]);

  useEffect(() => {
    if (activeTab === 'experiences') { fetchExperiences(); }
  }, [activeTab, fetchExperiences]);

  useEffect(() => {
    if (activeTab === 'settings') { fetchInsights(); }
  }, [activeTab, fetchInsights]);

  useEffect(() => {
    if (!id || versions.length === 0) return;
    const expanded = Array.from(expandedVersions);
    expanded.forEach((versionId) => {
      api.listTodos({ project_id: id, version_id: versionId }).then((todos) => {
        setVersionTodos((prev) => ({ ...prev, [versionId]: todos }));
      }).catch(() => {});
    });
  }, [id, versions, expandedVersions]);

  const toggleVersion = (versionId: string) => {
    setExpandedVersions((prev) => {
      const next = new Set(prev);
      if (next.has(versionId)) next.delete(versionId);
      else next.add(versionId);
      return next;
    });
  };

  const handleSave = async () => {
    if (!id || !project) return;
    try {
      const updated = await api.updateProject(id, form);
      setProject(updated);
      setDirty(false);
      toast('已保存', 'success');
    } catch {
      toast('保存失败', 'error');
    }
  };

  const handleCreateVersion = async () => {
    if (!id) return;
    try {
      await api.createVersion(id, {
        name: versionName.trim() || undefined,
        goal: versionGoal.trim(),
        version_type: versionType,
      });
      setShowNewVersion(false);
      setVersionName('');
      setVersionGoal('');
      setVersionType('minor');
      const v = await api.listVersions(id);
      setVersions(v);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '创建版本失败';
      toast(msg, 'error');
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    if (!id) return;
    try {
      await api.activateVersion(id, versionId);
      const v = await api.listVersions(id);
      setVersions(v);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '激活版本失败';
      toast(msg, 'error');
    }
  };

  const handleReleaseVersion = async (versionId: string) => {
    if (!id) return;
    try {
      await api.releaseVersion(id, versionId);
      const v = await api.listVersions(id);
      setVersions(v);
      toast('版本已发布', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '发布版本失败';
      toast(msg, 'error');
    }
  };

  const handleCreateTodo = async (title: string, description: string) => {
    if (!id || !createForVersion) return;
    try {
      const todo = await api.createTodo({ title, description, project_id: id, version_id: createForVersion });
      setVersionTodos((prev) => ({
        ...prev,
        [createForVersion]: [todo, ...(prev[createForVersion] || [])],
      }));
      api.extractTags(todo.id).then((updated) => {
        setVersionTodos((prev) => ({
          ...prev,
          [createForVersion]: (prev[createForVersion] || []).map((t) => (t.id === updated.id ? updated : t)),
        }));
      }).catch(() => {});
      navigate(`/todo/${todo.id}`);
    } catch {
      toast('创建需求失败', 'error');
    }
  };

  const handleDeleteTodo = async (todoId: string, todoTitle: string, versionId: string) => {
    if (!window.confirm(`确定删除需求「${todoTitle}」？此操作不可撤销。`)) return;
    try {
      await api.deleteTodo(todoId);
      setVersionTodos((prev) => ({
        ...prev,
        [versionId]: (prev[versionId] || []).filter((t) => t.id !== todoId),
      }));
      toast('需求已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  const handleConfirmExp = async (expId: string) => {
    try {
      await api.confirmExperience(expId);
      fetchExperiences();
    } catch {
      toast('确认失败', 'error');
    }
  };

  const handleArchiveExp = async (expId: string) => {
    try {
      await api.archiveExperience(expId);
      fetchExperiences();
    } catch {
      toast('归档失败', 'error');
    }
  };

  const handlePromoteExp = async (expId: string) => {
    try {
      await api.promoteExperience(expId);
      fetchExperiences();
      toast('已升级为个人经验', 'success');
    } catch {
      toast('升级失败', 'error');
    }
  };

  const handleAppendConvention = (solution: string) => {
    const sep = form.conventions.trim() ? '\n\n' : '';
    setForm({ ...form, conventions: form.conventions + sep + solution });
    setDirty(true);
    toast('已添加到规范，记得保存', 'success');
  };

  const handleArchiveProject = async () => {
    if (!id) return;
    try {
      await api.archiveProject(id);
      toast('项目已归档', 'success');
      navigate('/');
    } catch {
      toast('归档失败', 'error');
    }
  };

  const handleDeleteProject = async () => {
    if (!id || !project) return;
    if (!window.confirm(`确定删除项目「${project.name}」？此操作不可撤销。`)) return;
    try {
      await api.deleteProject(id);
      toast('项目已删除', 'success');
      navigate('/');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  const handleDeleteVersion = async (versionId: string, versionName: string) => {
    if (!id) return;
    if (!window.confirm(`确定删除版本「${versionName}」？此操作不可撤销。`)) return;
    try {
      await api.deleteVersion(id, versionId);
      const v = await api.listVersions(id);
      setVersions(v);
      toast('版本已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  if (loading || !project) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <div className="h-7 w-7 animate-pulse rounded-md bg-border/50" />
          <div className="h-5 w-32 animate-pulse rounded bg-border/50" />
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div>
            <VersionListSkeleton />
          </div>
        </div>
      </div>
    );
  }

  const projectActions: ActionMenuItem[] = [
    ...(project.status !== 'archived' ? [{ label: '归档项目', icon: <Archive size={12} />, onClick: handleArchiveProject }] : []),
    { label: '删除项目', icon: <Trash2 size={12} />, danger: true, onClick: handleDeleteProject },
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-6 py-4">
        <button
          onClick={() => navigate('/')}
          className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-bg-elevated hover:text-text-secondary"
        >
          <ArrowLeft size={16} />
        </button>
        <h1 className="font-heading text-lg font-semibold text-text-primary">{project.name}</h1>
        <ActionMenu items={projectActions} />

        {/* Tab bar */}
        <nav className="ml-6 flex gap-1">
          {TAB_ITEMS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === key
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-tertiary hover:bg-bg-elevated hover:text-text-secondary'
              }`}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="animate-fade-in">
          {activeTab === 'todos' && (
            <TodosTab
              versions={versions}
              versionTodos={versionTodos}
              expandedVersions={expandedVersions}
              toggleVersion={toggleVersion}
              showNewVersion={showNewVersion}
              setShowNewVersion={setShowNewVersion}
              versionName={versionName}
              setVersionName={setVersionName}
              versionGoal={versionGoal}
              setVersionGoal={setVersionGoal}
              versionType={versionType}
              setVersionType={setVersionType}
              handleCreateVersion={handleCreateVersion}
              handleActivateVersion={handleActivateVersion}
              handleReleaseVersion={handleReleaseVersion}
              handleDeleteVersion={handleDeleteVersion}
              handleDeleteTodo={handleDeleteTodo}
              setCreateForVersion={setCreateForVersion}
              navigate={navigate}
            />
          )}

          {activeTab === 'experiences' && (
            <ExperiencesTab
              experiences={experiences}
              loading={expLoading}
              filter={expFilter}
              setFilter={setExpFilter}
              onConfirm={handleConfirmExp}
              onArchive={handleArchiveExp}
              onPromote={handlePromoteExp}
            />
          )}

          {activeTab === 'settings' && (
            <SettingsTab
              form={form}
              setForm={(f) => { setForm(f); setDirty(true); }}
              dirty={dirty}
              onSave={handleSave}
              insights={insights}
              onAppendConvention={handleAppendConvention}
            />
          )}
        </div>
      </div>

      <CreateTodoModal
        open={!!createForVersion}
        onClose={() => setCreateForVersion(null)}
        onCreate={handleCreateTodo}
        projectId={id!}
        versionId={createForVersion || ''}
        versionName={versions.find((v) => v.id === createForVersion)?.name}
      />
    </div>
  );
}

// ─── Todos Tab ──────────────────────────────────────────

function TodosTab({
  versions,
  versionTodos,
  expandedVersions,
  toggleVersion,
  showNewVersion,
  setShowNewVersion,
  versionName,
  setVersionName,
  versionGoal,
  setVersionGoal,
  versionType,
  setVersionType,
  handleCreateVersion,
  handleActivateVersion,
  handleReleaseVersion,
  handleDeleteVersion,
  handleDeleteTodo,
  setCreateForVersion,
  navigate,
}: {
  versions: Version[];
  versionTodos: Record<string, Todo[]>;
  expandedVersions: Set<string>;
  toggleVersion: (id: string) => void;
  showNewVersion: boolean;
  setShowNewVersion: (v: boolean) => void;
  versionName: string;
  setVersionName: (v: string) => void;
  versionGoal: string;
  setVersionGoal: (v: string) => void;
  versionType: VersionType;
  setVersionType: (v: VersionType) => void;
  handleCreateVersion: () => void;
  handleActivateVersion: (id: string) => void;
  handleReleaseVersion: (id: string) => void;
  handleDeleteVersion: (id: string, name: string) => void;
  handleDeleteTodo: (todoId: string, todoTitle: string, versionId: string) => void;
  setCreateForVersion: (id: string) => void;
  navigate: (path: string) => void;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <GitBranch size={13} /> 版本 & 需求
        </h2>
        <button
          onClick={() => setShowNewVersion(true)}
          className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary"
        >
          <Plus size={12} /> 新版本
        </button>
      </div>

      {showNewVersion && (
        <div className="mb-3 rounded-lg border border-accent/30 bg-bg-card p-4">
          <div className="mb-3">
            <input
              type="text"
              value={versionGoal}
              onChange={(e) => setVersionGoal(e.target.value)}
              placeholder="版本目标（一句话描述本迭代要做什么）"
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
              autoFocus
            />
          </div>
          <div className="mb-3 flex gap-2">
            {([
              { key: 'major', label: '大版本', desc: 'x.0' },
              { key: 'minor', label: '功能迭代', desc: '_.x' },
              { key: 'patch', label: '修复补丁', desc: '_._.x' },
            ] as const).map((t) => (
              <button
                key={t.key}
                onClick={() => setVersionType(t.key)}
                className={`flex-1 rounded-md border px-2 py-1.5 text-center text-[11px] font-medium transition-colors ${
                  versionType === t.key
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-text-tertiary hover:text-text-secondary'
                }`}
              >
                {t.label} <span className="text-text-muted">({t.desc})</span>
              </button>
            ))}
          </div>
          <div className="mb-3">
            <input
              type="text"
              value={versionName}
              onChange={(e) => setVersionName(e.target.value)}
              placeholder="版本号（留空按类型自动生成）"
              className="h-8 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowNewVersion(false)} className="rounded-md border border-border px-3 py-1 text-xs text-text-secondary">取消</button>
            <button onClick={handleCreateVersion} className="rounded-md bg-accent px-3 py-1 text-xs text-white hover:bg-accent-hover">创建</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {versions.length === 0 && !showNewVersion && (
          <p className="rounded-lg border border-border bg-bg-card p-4 text-center text-xs text-text-muted">
            还没有版本。创建一个版本来圈定需求范围。
          </p>
        )}
        {versions.map((v) => {
          const style = VERSION_STATUS_STYLE[v.status];
          const isExpanded = expandedVersions.has(v.id);
          const todos = versionTodos[v.id] || [];
          const stats = v.todo_stats;
          const total = stats?.total ?? 0;
          const done = stats?.done ?? 0;
          const pct = total > 0 ? Math.round((done / total) * 100) : 0;

          return (
            <div key={v.id} className="rounded-lg border border-border bg-bg-card">
              <div className="flex items-center justify-between px-4 py-3">
                <button
                  onClick={() => toggleVersion(v.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  {isExpanded ? (
                    <ChevronDown size={14} className="flex-shrink-0 text-text-muted" />
                  ) : (
                    <ChevronRight size={14} className="flex-shrink-0 text-text-muted" />
                  )}
                  <span className="text-sm font-medium text-text-primary">{v.name}</span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${style.bg}`}>
                    {style.label}
                  </span>
                  {total > 0 && (
                    <span className="text-[10px] text-text-muted">{done}/{total} 完成</span>
                  )}
                </button>
                <div className="ml-3 flex items-center gap-1.5">
                  {v.status !== 'released' && (
                    <button
                      onClick={() => setCreateForVersion(v.id)}
                      className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-accent hover:text-accent"
                    >
                      <Plus size={10} /> 需求
                    </button>
                  )}
                  <ActionMenu items={(() => {
                    const items: ActionMenuItem[] = [];
                    if (v.status === 'planning') {
                      items.push({ label: '开始迭代', icon: <Play size={12} />, onClick: () => handleActivateVersion(v.id) });
                    }
                    if (v.status === 'active') {
                      items.push({ label: '发布版本', icon: <CheckCircle size={12} />, onClick: () => handleReleaseVersion(v.id) });
                    }
                    if (v.status !== 'released') {
                      items.push({ label: '删除版本', icon: <Trash2 size={12} />, danger: true, onClick: () => handleDeleteVersion(v.id, v.name) });
                    }
                    return items;
                  })()} />
                </div>
              </div>

              {/* Progress bar */}
              {total > 0 && (
                <div className="px-4 pb-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border/30">
                      <div
                        className="h-full rounded-full bg-status-done transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-[10px] tabular-nums text-text-muted">{pct}%</span>
                  </div>
                  {stats && (
                    <div className="mt-1 flex gap-3 text-[10px] text-text-muted">
                      {stats.pending > 0 && <span>{stats.pending} 待启动</span>}
                      {stats.active > 0 && <span>{stats.active} 进行中</span>}
                      {stats.done > 0 && <span>{stats.done} 已完成</span>}
                      {stats.error > 0 && <span className="text-status-error">{stats.error} 异常</span>}
                    </div>
                  )}
                </div>
              )}

              {v.goal && isExpanded && (
                <div className="border-t border-border/50 px-4 py-2">
                  <p className="text-xs text-text-secondary">{v.goal}</p>
                </div>
              )}

              {/* Changelog for released versions */}
              {v.status === 'released' && v.changelog && isExpanded && (
                <div className="border-t border-border/50 px-4 py-2">
                  <p className="mb-1 text-[10px] font-medium text-text-tertiary">变更记录</p>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">{v.changelog}</p>
                </div>
              )}

              {isExpanded && (
                <div className="border-t border-border/50">
                  {todos.length === 0 ? (
                    <p className="px-4 py-3 text-center text-[11px] text-text-muted">
                      暂无需求，点击"+ 需求"添加
                    </p>
                  ) : (
                    <div className="divide-y divide-border/30">
                      {todos.map((todo) => (
                        <div
                          key={todo.id}
                          onClick={() => navigate(`/todo/${todo.id}`)}
                          className="group flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors hover:bg-bg-elevated"
                        >
                          <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${statusDotColor[todo.status]}`} />
                          <span className="min-w-0 flex-1 truncate text-xs text-text-primary">{todo.title}</span>
                          <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${statusBadgeBg[todo.status]}`}>
                            {STATUS_LABELS[todo.status]}
                          </span>
                          {todo.current_phase && <PhaseProgress currentPhase={todo.current_phase} />}
                          <div className="flex flex-shrink-0 gap-1">
                            {todo.tags.slice(0, 2).map((tag) => (
                              <span
                                key={tag.label}
                                className="rounded px-1 py-0.5 text-[9px] font-medium"
                                style={{ backgroundColor: `${tag.color}18`, color: tag.color }}
                              >
                                {tag.label}
                              </span>
                            ))}
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDeleteTodo(todo.id, todo.title, v.id); }}
                            className="flex-shrink-0 rounded p-1 text-text-muted opacity-0 transition-all hover:bg-status-error/10 hover:text-status-error group-hover:opacity-100"
                            title="删除需求"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ─── Experiences Tab ────────────────────────────────────

function ExperiencesTab({
  experiences,
  loading,
  filter,
  setFilter,
  onConfirm,
  onArchive,
  onPromote,
}: {
  experiences: Experience[];
  loading: boolean;
  filter: 'all' | 'draft' | 'confirmed';
  setFilter: (f: 'all' | 'draft' | 'confirmed') => void;
  onConfirm: (id: string) => void;
  onArchive: (id: string) => void;
  onPromote: (id: string) => void;
}) {
  const filters: { key: typeof filter; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'draft', label: '待审核' },
    { key: 'confirmed', label: '已确认' },
  ];

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Lightbulb size={13} /> 项目经验
        </h2>
        <div className="flex gap-1">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                filter === f.key
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-tertiary hover:text-text-secondary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="py-8 text-center text-xs text-text-muted">加载中...</p>
      ) : experiences.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-6 text-center">
          <Lightbulb size={28} className="mx-auto mb-2 text-text-muted" strokeWidth={1.2} />
          <p className="text-xs text-text-secondary">暂无经验</p>
          <p className="mt-1 text-[11px] text-text-muted">完成需求后，AI会自动提取经验</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {experiences.map((exp) => {
            const style = expStatusStyle[exp.status];
            return (
              <div key={exp.id} className="rounded-lg border border-border bg-bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${style.dot}`} />
                      <h3 className="truncate text-sm font-medium text-text-primary">{exp.title}</h3>
                      <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${style.bg}`}>
                        {EXPERIENCE_STATUS_LABELS[exp.status]}
                      </span>
                      {exp.scope === 'personal' && (
                        <span className="rounded-full bg-purple-500/15 px-1.5 py-0.5 text-[9px] font-medium text-purple-500">
                          个人
                        </span>
                      )}
                    </div>
                    {exp.problem && (
                      <p className="mt-1.5 line-clamp-2 text-xs text-text-secondary">{exp.problem}</p>
                    )}
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-text-muted">
                      <span>信心 {Math.round(exp.confidence * 100)}%</span>
                      <span>复用 {exp.reuse_count} 次</span>
                      {exp.tags.length > 0 && (
                        <div className="flex gap-1">
                          {exp.tags.slice(0, 3).map((t) => (
                            <span key={t.label} className="rounded px-1 py-0.5" style={{ backgroundColor: `${t.color}18`, color: t.color }}>
                              {t.label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1">
                    {exp.status === 'draft' && (
                      <button
                        onClick={() => onConfirm(exp.id)}
                        className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-status-done hover:text-status-done"
                        title="确认经验"
                      >
                        <Check size={10} /> 确认
                      </button>
                    )}
                    {exp.status !== 'archived' && (
                      <button
                        onClick={() => onArchive(exp.id)}
                        className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-text-muted hover:text-text-muted"
                        title="归档"
                      >
                        <Archive size={10} />
                      </button>
                    )}
                    {exp.scope === 'project' && exp.status === 'confirmed' && (
                      <button
                        onClick={() => onPromote(exp.id)}
                        className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-text-secondary hover:border-purple-500 hover:text-purple-500"
                        title="升级为个人经验"
                      >
                        <ArrowUpRight size={10} /> 个人
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ─── Settings Tab ───────────────────────────────────────

function SettingsTab({
  form,
  setForm,
  dirty,
  onSave,
  insights,
  onAppendConvention,
}: {
  form: { name: string; description: string; tech_stack: string; repo_url: string; conventions: string };
  setForm: (f: typeof form) => void;
  dirty: boolean;
  onSave: () => void;
  insights: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>;
  onAppendConvention: (solution: string) => void;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Settings size={13} /> 项目设置
        </h2>
        <button
          onClick={onSave}
          disabled={!dirty}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white transition-opacity hover:bg-accent-hover disabled:opacity-30"
        >
          <Save size={12} /> 保存更改
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">基本信息</p>
          <Field label="项目名称" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
          <Field label="描述" value={form.description} onChange={(v) => setForm({ ...form, description: v })} multiline />
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-4 space-y-4">
          <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide">技术配置</p>
          <Field label="技术栈" value={form.tech_stack} onChange={(v) => setForm({ ...form, tech_stack: v })} placeholder="例如：React + FastAPI + PostgreSQL" />
          <Field label="代码仓库" value={form.repo_url} onChange={(v) => setForm({ ...form, repo_url: v })} placeholder="https://github.com/..." />
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">项目规范</p>
          <Field label="规范内容" value={form.conventions} onChange={(v) => setForm({ ...form, conventions: v })} multiline placeholder="AI在生成方案和代码时会遵守这些规范" />
        </div>

        {insights.length > 0 && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 lg:col-span-2">
            <p className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-amber-600">
              <Lightbulb size={13} /> 规范建议
            </p>
            <p className="mb-3 text-[11px] text-text-muted">以下经验已多次验证有效，建议纳入项目规范</p>
            <div className="space-y-2">
              {insights.map((ins) => (
                <div key={ins.id} className="flex items-start gap-3 rounded-md border border-amber-500/15 bg-bg-card p-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-text-primary">{ins.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-text-secondary">{ins.solution}</p>
                    <div className="mt-1 flex gap-2 text-[10px] text-text-muted">
                      <span>信心 {Math.round(ins.confidence * 100)}%</span>
                      <span>复用 {ins.reuse_count} 次</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onAppendConvention(ins.solution)}
                    className="flex-shrink-0 rounded-md border border-amber-500/30 px-2 py-1 text-[10px] font-medium text-amber-600 hover:bg-amber-500/10"
                  >
                    纳入规范
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

// ─── Shared Components ──────────────────────────────────

function AutoTextarea({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={1}
      className={className}
    />
  );
}

function Field({
  label,
  value,
  onChange,
  multiline,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-text-tertiary">{label}</label>
      {multiline ? (
        <AutoTextarea
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="min-h-[4.5rem] w-full resize-y rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
        />
      )}
    </div>
  );
}
