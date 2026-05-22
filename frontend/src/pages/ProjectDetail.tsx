import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Lightbulb, Settings, Archive, Trash2, Sparkles, Loader2, Users } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/Toast';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { useAuth } from '../contexts/AuthContext';
import { useProjectTaskStream } from '../hooks/useProjectTaskStream';
import ActionMenu from '../components/ActionMenu';
import type { ActionMenuItem } from '../components/ActionMenu';
import type { Project, Version, VersionType, Todo, Experience, ExperienceCategory, PlanningSession, UserRole } from '../types/api';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';
import MarkdownContent from '../components/MarkdownContent';
import DeliverableDrawer from '../components/DeliverableDrawer';
import { TodosTab, SettingsTab, ExperiencesTab } from '../components/project';

type TabKey = 'todos' | 'experiences' | 'settings';

const TAB_ITEMS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: 'todos', label: '需求', icon: FileText },
  { key: 'experiences', label: '经验', icon: Lightbulb },
  { key: 'settings', label: '设置', icon: Settings },
];


export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setProject: setCurrentProject } = useCurrentProject();
  const { user: authUser } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionTodos, setVersionTodos] = useState<Record<string, Todo[]>>({});
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('todos');

  // Settings form
  const [form, setForm] = useState({
    name: '', description: '', tech_stack: '', repo_url: '', local_path: '', conventions: '', codebase_summary: '',
    execution_mode: 'pipeline' as 'pipeline' | 'conversation',
    pipeline_config: {} as Record<string, unknown>,
    conversation_config: {} as Record<string, unknown>,
  });
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
  const [expCategoryFilter, setExpCategoryFilter] = useState<ExperienceCategory | 'all'>('all');
  const [expLoading, setExpLoading] = useState(false);

  // Insights
  const [insights, setInsights] = useState<Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>>([]);

  // Project role for current user
  const [myRole, setMyRole] = useState<UserRole>('admin');

  // Task stream for conversation mode
  const isConversationMode = form.execution_mode === 'conversation';
  const { getTaskState } = useProjectTaskStream(isConversationMode ? id : undefined);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, v, members] = await Promise.all([api.getProject(id), api.listVersions(id), api.listMembers(id).catch(() => [])]);
      setProject(p);
      setCurrentProject({ id: p.id, name: p.name });
      setVersions(v);
      if (authUser) {
        const me = members.find(m => m.user_id === authUser.id);
        setMyRole(me?.role ?? 'admin');
      }
      setForm({
        name: p.name,
        description: p.description,
        tech_stack: p.tech_stack,
        repo_url: p.repo_url,
        local_path: p.local_path || '',
        conventions: p.conventions,
        codebase_summary: p.codebase_summary || '',
        execution_mode: p.execution_mode || 'pipeline',
        pipeline_config: p.pipeline_config || {},
        conversation_config: p.conversation_config || {},
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
      const category = expCategoryFilter === 'all' ? undefined : expCategoryFilter;
      const exps = await api.listProjectExperiences(id, { status, category });
      setExperiences(exps);
    } catch {
      setExperiences([]);
    } finally {
      setExpLoading(false);
    }
  }, [id, expFilter, expCategoryFilter]);

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
      }).catch((err) => { console.warn('Failed to load todos for version:', versionId, err); });
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
      }).catch((err) => { console.warn('Failed to extract tags:', err); });
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

  const handleDistillExp = async (expId: string) => {
    try {
      await api.distillExperience(expId);
      fetchExperiences();
      toast('已提炼为个人经验', 'success');
    } catch {
      toast('提炼失败', 'error');
    }
  };

  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Drawer for roadmap preview
  const [drawerSession, setDrawerSession] = useState<PlanningSession | null>(null);

  const handleAnalyzeVersion = async (versionId: string) => {
    if (!id) return;
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const { analysis } = await api.analyzeIteration(id, versionId);
      setAnalysisResult(analysis);
    } catch (err) {
      toast(`分析失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
    } finally {
      setAnalyzing(false);
    }
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

  const isAdmin = myRole === 'admin';
  const canWrite = myRole === 'admin' || myRole === 'member';

  const projectActions: ActionMenuItem[] = isAdmin ? [
    ...(project.status !== 'archived' ? [{ label: '归档项目', icon: <Archive size={12} />, onClick: handleArchiveProject }] : []),
    { label: '删除项目', icon: <Trash2 size={12} />, danger: true, onClick: handleDeleteProject },
  ] : [];

  const visibleTabs = TAB_ITEMS.filter(t => {
    if (t.key === 'settings') return isAdmin;
    return true;
  });

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
        {projectActions.length > 0 && <ActionMenu items={projectActions} />}

        {/* Tab bar */}
        <nav className="ml-6 flex gap-1">
          {visibleTabs.map(({ key, label, icon: Icon }) => (
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
              projectId={id!}
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
              onAnalyzeVersion={handleAnalyzeVersion}
              onRefreshData={fetchData}
              onPreviewRoadmap={(session) => setDrawerSession(session)}
              executionMode={form.execution_mode}
              getTaskState={isConversationMode ? getTaskState : undefined}
              onBatchStart={isConversationMode ? async (todoIds) => {
                await api.batchStartConversations(id!, todoIds);
                fetchData();
              } : undefined}
              canWrite={canWrite}
            />
          )}

          {activeTab === 'experiences' && (
            <ExperiencesTab
              experiences={experiences}
              loading={expLoading}
              filter={expFilter}
              setFilter={setExpFilter}
              categoryFilter={expCategoryFilter}
              setCategoryFilter={setExpCategoryFilter}
              onConfirm={handleConfirmExp}
              onArchive={handleArchiveExp}
              onPromote={handlePromoteExp}
              onDistill={handleDistillExp}
            />
          )}

          {activeTab === 'settings' && (
            <SettingsTab
              projectId={id!}
              form={form}
              setForm={(f) => { setForm(f); setDirty(true); }}
              dirty={dirty}
              onSave={handleSave}
              onRefresh={fetchData}
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

      {/* Iteration Analysis Modal */}
      {(analyzing || analysisResult) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => { setAnalysisResult(null); setAnalyzing(false); }} />
          <div className="relative mx-4 w-full max-w-2xl animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h2 className="flex items-center gap-2 font-heading text-sm font-semibold text-text-primary">
                <Sparkles size={14} className="text-accent" /> AI 迭代分析
              </h2>
              <button
                onClick={() => { setAnalysisResult(null); setAnalyzing(false); }}
                className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary"
              >
                ×
              </button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
              {analyzing ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={20} className="animate-spin text-accent" />
                  <span className="ml-2 text-sm text-text-muted">AI 正在分析迭代状态...</span>
                </div>
              ) : analysisResult ? (
                <MarkdownContent content={analysisResult} />
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Roadmap Preview Drawer */}
      <DeliverableDrawer
        open={!!drawerSession}
        onClose={() => setDrawerSession(null)}
        content={drawerSession ? { type: 'roadmap', data: drawerSession } : null}
      />
    </div>
  );
}
