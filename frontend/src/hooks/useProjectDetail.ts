import { useState, useEffect, useCallback, createElement } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Archive, Trash2 } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/Toast';
import { useConfirm } from '../components/ConfirmProvider';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { useAuth } from '../contexts/AuthContext';
import { useProjectTaskStream } from './useProjectTaskStream';
import { useExperiences } from './useExperiences';
import { useDomainModel } from './useDomainModel';
import { useDomainModelReview } from './useDomainModelReview';
import { useVersionActions } from './useVersionActions';
import { useTodoActions } from './useTodoActions';
import { useVersionAnalysis } from './useVersionAnalysis';
import type { ActionMenuItem } from '../components/ActionMenu';
import type { Project, Version, Todo, PlanningSession, UserRole } from '../types/api';

type TabKey = 'todos' | 'experiences' | 'domain_model' | 'settings';

export function useProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const confirm = useConfirm();
  const { setProject: setCurrentProject } = useCurrentProject();
  const { user: authUser } = useAuth();

  // ── Core state ──────────────────────────────────────────
  const [project, setProject] = useState<Project | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionTodos, setVersionTodos] = useState<Record<string, Todo[]>>({});
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('todos');
  const [drawerSession, setDrawerSession] = useState<PlanningSession | null>(null);
  const [myRole, setMyRole] = useState<UserRole>('admin');

  // ── Settings form ───────────────────────────────────────
  const [form, setForm] = useState({
    name: '', description: '', tech_stack: '', repo_url: '', local_path: '', conventions: '', codebase_summary: '',
    process_constraint: 'free' as 'strict' | 'moderate' | 'free',
    pipeline_config: {} as Record<string, unknown>,
    conversation_config: {} as Record<string, unknown>,
  });
  const [dirty, setDirty] = useState(false);

  // ── Data fetching ───────────────────────────────────────
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
        name: p.name, description: p.description, tech_stack: p.tech_stack,
        repo_url: p.repo_url, local_path: p.local_path || '',
        conventions: p.conventions, codebase_summary: p.codebase_summary || '',
        process_constraint: p.process_constraint || 'free',
        pipeline_config: p.pipeline_config || {},
        conversation_config: p.conversation_config || {},
      });
      setDirty(false);
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

  const refreshVersions = useCallback(async () => {
    if (!id) return;
    const v = await api.listVersions(id);
    setVersions(v);
  }, [id]);

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

  // ── Composed hooks ──────────────────────────────────────
  const isConversationMode = form.process_constraint !== 'strict';
  const { getTaskState } = useProjectTaskStream(isConversationMode ? id : undefined);

  const { experiences, expLoading, expFilter, setExpFilter, expCategoryFilter, setExpCategoryFilter, insights, fetchExperiences } = useExperiences(id, activeTab);
  const { domainModel, domainModelLoading, fetchDomainModel } = useDomainModel(id, activeTab);
  const domainModelReview = useDomainModelReview(id, domainModel?.version || 0);

  const versionActions = useVersionActions(id, toast, refreshVersions, confirm);
  const todoActions = useTodoActions(id, navigate, toast, versionTodos, setVersionTodos, fetchData, versions, confirm);
  const analysis = useVersionAnalysis(id, versions, setVersions, toast);

  // ── Simple handlers ─────────────────────────────────────
  const toggleVersion = (versionId: string) => {
    setExpandedVersions((prev) => {
      const next = new Set(prev);
      if (next.has(versionId)) next.delete(versionId); else next.add(versionId);
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
    } catch { toast('保存失败', 'error'); }
  };

  // ── Experience handlers ─────────────────────────────────
  const handleConfirmExp = async (expId: string) => { try { await api.confirmExperience(expId); fetchExperiences(); } catch { toast('确认失败', 'error'); } };
  const handleArchiveExp = async (expId: string) => { try { await api.archiveExperience(expId); fetchExperiences(); } catch { toast('归档失败', 'error'); } };
  const handlePromoteExp = async (expId: string) => { try { await api.promoteExperience(expId); fetchExperiences(); toast('已升级为个人经验', 'success'); } catch { toast('升级失败', 'error'); } };
  const handleDistillExp = async (expId: string) => { try { await api.distillExperience(expId); fetchExperiences(); toast('已提炼为个人经验', 'success'); } catch { toast('提炼失败', 'error'); } };
  const handleAppendConvention = (solution: string) => {
    const sep = form.conventions.trim() ? '\n\n' : '';
    setForm({ ...form, conventions: form.conventions + sep + solution });
    setDirty(true);
    toast('已添加到规范，记得保存', 'success');
  };

  // ── Domain model handlers ───────────────────────────────
  const [extracting, setExtracting] = useState(false);
  const [refreshingDM, setRefreshingDM] = useState(false);
  const [extractingDMFromCode, setExtractingDMFromCode] = useState(false);

  const handleExtractExperiences = async () => { if (!id) return; setExtracting(true); try { const r = await api.extractProjectExperiences(id); toast(`提取完成: ${r.extracted} 条新经验, ${r.skipped} 条跳过`, 'success'); fetchExperiences(); } catch { toast('经验提取失败', 'error'); } finally { setExtracting(false); } };
  const handleRefreshDomainModel = async () => { if (!id) return; setRefreshingDM(true); try { const r = await api.refreshDomainModel(id); toast(`领域模型已刷新, 合并 ${r.merged} 个交付物`, 'success'); fetchDomainModel(); } catch { toast('领域模型刷新失败', 'error'); } finally { setRefreshingDM(false); } };
  const handleExtractDomainModelFromCode = async () => { if (!id) return; setExtractingDMFromCode(true); try { await api.extractDomainModelFromCode(id); toast('领域模型已从代码库提取', 'success'); fetchDomainModel(); } catch (err) { toast(err instanceof Error ? err.message : '提取失败', 'error'); } finally { setExtractingDMFromCode(false); } };

  // ── Project actions ─────────────────────────────────────
  const handleArchiveProject = async () => { if (!id) return; try { await api.archiveProject(id); toast('项目已归档', 'success'); navigate('/'); } catch { toast('归档失败', 'error'); } };
  const handleDeleteProject = async () => { if (!id || !project) return; const ok = await confirm({ title: '删除项目', message: `确定删除项目「${project.name}」？此操作不可撤销。`, confirmLabel: '删除', variant: 'danger' }); if (!ok) return; try { await api.deleteProject(id); toast('项目已删除', 'success'); navigate('/'); } catch (err) { toast(err instanceof ApiError ? err.detail : '删除失败', 'error'); } };

  const isAdmin = myRole === 'admin';
  const canWrite = myRole === 'admin' || myRole === 'member';
  const projectActions: ActionMenuItem[] = isAdmin ? [
    ...(project?.status !== 'archived' ? [{ label: '归档项目', icon: createElement(Archive, { size: 12 }), onClick: handleArchiveProject }] : []),
    { label: '删除项目', icon: createElement(Trash2, { size: 12 }), danger: true, onClick: handleDeleteProject },
  ] : [];

  // ── Return ──────────────────────────────────────────────
  return {
    id, navigate, project, loading,
    activeTab, setActiveTab,
    versions, versionTodos, expandedVersions, toggleVersion,
    form, setForm: (f: typeof form) => { setForm(f); setDirty(true); },
    dirty, handleSave,
    ...versionActions,
    ...todoActions,
    ...analysis,
    experiences, expLoading, expFilter, setExpFilter,
    expCategoryFilter, setExpCategoryFilter,
    handleConfirmExp, handleArchiveExp, handlePromoteExp, handleDistillExp,
    insights, handleAppendConvention,
    domainModel, domainModelLoading, handleRefreshDomainModel, refreshingDM,
    domainModelReview,
    handleExtractDomainModelFromCode, extractingDMFromCode,
    handleExtractExperiences, extracting,
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
