import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Archive, Trash2 } from 'lucide-react';
import { createElement } from 'react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/Toast';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { useAuth } from '../contexts/AuthContext';
import { useProjectTaskStream } from './useProjectTaskStream';
import { useExperiences } from './useExperiences';
import { useDomainModel } from './useDomainModel';
import { useDomainModelReview } from './useDomainModelReview';
import type { ActionMenuItem } from '../components/ActionMenu';
import type { Project, Version, VersionType, Todo, PlanningSession, UserRole } from '../types/api';

type TabKey = 'todos' | 'experiences' | 'domain_model' | 'settings';

export function useProjectDetail() {
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

  const [form, setForm] = useState({
    name: '', description: '', tech_stack: '', repo_url: '', local_path: '', conventions: '', codebase_summary: '',
    execution_mode: 'pipeline' as 'pipeline' | 'conversation',
    process_constraint: 'free' as 'strict' | 'moderate' | 'free',
    pipeline_config: {} as Record<string, unknown>,
    conversation_config: {} as Record<string, unknown>,
  });
  const [dirty, setDirty] = useState(false);

  const [showNewVersion, setShowNewVersion] = useState(false);
  const [versionName, setVersionName] = useState('');
  const [versionGoal, setVersionGoal] = useState('');
  const [versionType, setVersionType] = useState<VersionType>('minor');

  const [createForVersion, setCreateForVersion] = useState<string | null>(null);

  const {
    experiences, expLoading, expFilter, setExpFilter,
    expCategoryFilter, setExpCategoryFilter,
    insights, fetchExperiences,
  } = useExperiences(id, activeTab);

  const { domainModel, domainModelLoading, fetchDomainModel } = useDomainModel(id, activeTab);
  const domainModelReview = useDomainModelReview(id, domainModel?.version || 0);

  const [myRole, setMyRole] = useState<UserRole>('admin');

  const isConversationMode = form.execution_mode === 'conversation';
  const { getTaskState } = useProjectTaskStream(isConversationMode ? id : undefined);

  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisCached, setAnalysisCached] = useState(false);
  const [analysisSuggestions, setAnalysisSuggestions] = useState<Array<{priority: string; action: string; reason: string}>>([]);
  const [drawerSession, setDrawerSession] = useState<PlanningSession | null>(null);
  const [completeConfirm, setCompleteConfirm] = useState<{ todoId: string; hasDeliverables: boolean } | null>(null);

  const fetchData = useCallback(async (opts?: { silent?: boolean }) => {
    if (!id) return;
    if (!opts?.silent) setLoading(true);
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
        process_constraint: (p as Record<string, unknown>).process_constraint as 'strict' | 'moderate' | 'free' || 'free',
        pipeline_config: p.pipeline_config || {},
        conversation_config: p.conversation_config || {},
      });
      setDirty(false);
      // 仅首次加载或非静默刷新时重置展开状态
      if (!opts?.silent) {
        const activeIds = new Set(v.filter((ver) => ver.status === 'active').map((ver) => ver.id));
        setExpandedVersions(activeIds.size > 0 ? activeIds : new Set(v.slice(0, 1).map((ver) => ver.id)));
      }
    } catch {
      navigate('/');
    } finally {
      setLoading(false);
    }
  }, [id, navigate, authUser, setCurrentProject]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => () => setCurrentProject(null), [setCurrentProject]);

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
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) return;
      toast('创建需求失败', 'error');
    }
  };

  const createTodoFromSuggestion = async (data: { title: string; description: string; priority: number }) => {
    if (!id) return;
    // 找到第一个 active 或 planning 版本作为目标
    const targetVersion = versions.find((v) => v.status === 'planning') || versions.find((v) => v.status === 'active');
    if (!targetVersion) {
      toast('没有可用的版本来承接新需求', 'error');
      return;
    }
    // 去重：检查目标版本中是否已有同名需求
    const existingTodos = versionTodos[targetVersion.id] || [];
    if (existingTodos.some((t) => t.title === data.title)) {
      toast('该需求已存在，跳过重复创建', 'warning');
      return;
    }
    try {
      await api.createTodo({
        title: data.title,
        description: data.description,
        project_id: id,
        version_id: targetVersion.id,
        priority: data.priority,
      });
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
      // 刷新版本数据以更新 todo_stats 计数
      fetchData({ silent: true });
      toast('需求已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  const handleResumeTodo = async (todoId: string) => {
    if (!id) return;
    try {
      await api.resumeSuspendedTodo(id, todoId);
      fetchData({ silent: true });
      toast('需求已恢复', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '恢复失败';
      toast(msg, 'error');
    }
  };

  const handleCompleteTodo = async (todoId: string) => {
    // 检查交付物产出情况，设置确认弹窗状态
    let hasDeliverables = false;
    try {
      const tracker = await api.getDeliverables(todoId);
      const produced = Object.values(tracker.deliverables || {}).filter(
        (s) => s === 'produced' || s === 'confirmed'
      );
      hasDeliverables = produced.length > 0;
    } catch { /* tracker 不存在视为无交付物 */ }

    setCompleteConfirm({ todoId, hasDeliverables });
  };

  const confirmCompleteTodo = async () => {
    if (!completeConfirm) return;
    try {
      await api.completeTodo(completeConfirm.todoId);
      fetchData({ silent: true });
      toast('需求已完成', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '操作失败';
      toast(msg, 'error');
    } finally {
      setCompleteConfirm(null);
    }
  };

  const handleReopenTodo = async (todoId: string) => {
    try {
      await api.reopenTodo(todoId);
      fetchData({ silent: true });
      toast('需求已恢复为进行中', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '操作失败';
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

  const [extracting, setExtracting] = useState(false);
  const [refreshingDM, setRefreshingDM] = useState(false);

  const handleExtractExperiences = async () => {
    if (!id) return;
    setExtracting(true);
    try {
      const result = await api.extractProjectExperiences(id);
      toast(`提取完成: ${result.extracted} 条新经验, ${result.skipped} 条跳过`, 'success');
      fetchExperiences();
    } catch {
      toast('经验提取失败', 'error');
    } finally {
      setExtracting(false);
    }
  };

  const handleRefreshDomainModel = async () => {
    if (!id) return;
    setRefreshingDM(true);
    try {
      const result = await api.refreshDomainModel(id);
      toast(`领域模型已刷新, 合并 ${result.merged} 个交付物`, 'success');
      fetchDomainModel();
    } catch {
      toast('领域模型刷新失败', 'error');
    } finally {
      setRefreshingDM(false);
    }
  };

  const [extractingDMFromCode, setExtractingDMFromCode] = useState(false);
  const handleExtractDomainModelFromCode = async () => {
    if (!id) return;
    setExtractingDMFromCode(true);
    try {
      await api.extractDomainModelFromCode(id);
      toast('领域模型已从代码库提取', 'success');
      fetchDomainModel();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '提取失败';
      toast(msg, 'error');
    } finally {
      setExtractingDMFromCode(false);
    }
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

  const handleAnalyzeVersion = async (versionId: string) => {
    if (!id) return;
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisCached(false);
    setAnalysisSuggestions([]);
    try {
      const result = await api.analyzeIteration(id, versionId);
      setAnalysisResult(result.analysis);
      setAnalysisCached(result.cached ?? false);
      setAnalysisSuggestions(result.suggestions ?? []);
      // 刷新 versions 列表让按钮状态更新（has_analysis / analysis_stale）
      if (!result.cached) {
        const v = await api.listVersions(id);
        setVersions(v);
      }
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

  const handleDeleteVersion = async (versionId: string, name: string) => {
    if (!id) return;
    if (!window.confirm(`确定删除版本「${name}」？此操作不可撤销。`)) return;
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

  const closeAnalysis = () => { setAnalysisResult(null); setAnalyzing(false); };

  const isAdmin = myRole === 'admin';
  const canWrite = myRole === 'admin' || myRole === 'member';

  const projectActions: ActionMenuItem[] = isAdmin ? [
    ...(project?.status !== 'archived' ? [{ label: '归档项目', icon: createElement(Archive, { size: 12 }), onClick: handleArchiveProject }] : []),
    { label: '删除项目', icon: createElement(Trash2, { size: 12 }), danger: true, onClick: handleDeleteProject },
  ] : [];

  return {
    id, navigate, project, loading,
    activeTab, setActiveTab,
    versions, versionTodos, expandedVersions, toggleVersion,
    form, setForm: (f: typeof form) => { setForm(f); setDirty(true); },
    dirty, handleSave,
    showNewVersion, setShowNewVersion,
    versionName, setVersionName,
    versionGoal, setVersionGoal,
    versionType, setVersionType,
    handleCreateVersion, handleActivateVersion, handleReleaseVersion, handleDeleteVersion,
    createForVersion, setCreateForVersion, handleCreateTodo, createTodoFromSuggestion,
    handleDeleteTodo, handleResumeTodo, handleCompleteTodo, handleReopenTodo,
    completeConfirm, setCompleteConfirm, confirmCompleteTodo,
    experiences, expLoading, expFilter, setExpFilter,
    expCategoryFilter, setExpCategoryFilter,
    handleConfirmExp, handleArchiveExp, handlePromoteExp, handleDistillExp,
    insights, handleAppendConvention,
    domainModel, domainModelLoading, handleRefreshDomainModel, refreshingDM,
    domainModelReview,
    handleExtractDomainModelFromCode, extractingDMFromCode,
    handleExtractExperiences, extracting,
    analysisResult, analyzing, analysisCached, analysisSuggestions, closeAnalysis, handleAnalyzeVersion,
    drawerSession, setDrawerSession,
    fetchData,
    isAdmin, canWrite, projectActions,
    isConversationMode, getTaskState: isConversationMode ? getTaskState : undefined,
    batchStart: isConversationMode ? async (todoIds: string[]) => {
      await api.batchStartConversations(id!, todoIds);
      fetchData({ silent: true });
    } : undefined,
  };
}
