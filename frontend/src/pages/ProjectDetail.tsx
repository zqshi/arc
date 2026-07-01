import { useState, useEffect } from 'react';
import { ArrowLeft, FileText, Lightbulb, Settings, Database } from 'lucide-react';
import ActionMenu from '../components/ActionMenu';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';
import DeliverableDrawer from '../components/DeliverableDrawer';
import { TodosTab, SettingsTab, ExperiencesTab, DomainModelTab } from '../components/project';
import { useProjectDetail } from '../hooks/useProjectDetail';
import { api } from '../api/client';
import { VersionPicker, PreviewButton, AnalysisModal } from './project-detail-parts';

type TabKey = 'todos' | 'experiences' | 'domain_model' | 'settings';

const TAB_ITEMS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: 'todos', label: '需求', icon: FileText },
  { key: 'experiences', label: '经验', icon: Lightbulb },
  { key: 'domain_model', label: '领域模型', icon: Database },
  { key: 'settings', label: '设置', icon: Settings },
];

export default function ProjectDetail() {
  const s = useProjectDetail();
  const [roadmapDrawerWidth, setRoadmapDrawerWidth] = useState(560);

  // ── 原型预览状态 ──
  const [protoStatus, setProtoStatus] = useState<{
    has_prototype: boolean;
    preview_url: string | null;
    total_pages: number;
    version_id: string | null;
  } | null>(null);
  const [protoVersionId, setProtoVersionId] = useState<string | null>(null);
  const [showVersionPicker, setShowVersionPicker] = useState(false);

  useEffect(() => {
    if (!s.id) return;
    api.getPrototypeStatus(s.id, protoVersionId ?? undefined)
      .then(setProtoStatus)
      .catch(() => setProtoStatus(null));
  }, [s.id, protoVersionId, s.versions]);

  const handlePreview = () => {
    if (!s.id) return;
    const token = localStorage.getItem('access_token') || '';
    const params = new URLSearchParams({ token });
    if (protoVersionId) params.set('version_id', protoVersionId);
    window.open(
      `${import.meta.env.VITE_API_URL || ''}/api/projects/${s.id}/prototype-preview?${params}`,
      '_blank',
    );
  };

  // 已发布版本列表（用于版本选择器）
  const previewableVersions = (s.versions || []).filter(
    v => v.status === 'active' || v.status === 'released',
  );
  const selectedVersion = previewableVersions.find(v => v.id === protoVersionId);
  const hasPrototype = protoStatus?.has_prototype ?? false;

  if (s.loading || !s.project) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <div className="h-7 w-7 animate-pulse rounded-md bg-border/50" />
          <div className="h-5 w-32 animate-pulse rounded bg-border/50" />
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div><VersionListSkeleton /></div>
        </div>
      </div>
    );
  }

  const visibleTabs = TAB_ITEMS.filter(t => {
    if (t.key === 'settings') return s.isAdmin;
    return true;
  });

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-6 py-4">
        <button
          onClick={() => s.navigate('/')}
          className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-bg-elevated hover:text-text-secondary"
        >
          <ArrowLeft size={16} />
        </button>
        <h1 className="font-heading text-lg font-semibold text-text-primary">{s.project.name}</h1>
        {s.projectActions.length > 0 && <ActionMenu items={s.projectActions} />}

        <nav className="ml-6 flex gap-1">
          {visibleTabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => s.setActiveTab(key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                s.activeTab === key
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-tertiary hover:bg-bg-elevated hover:text-text-secondary'
              }`}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          {/* 版本选择器 */}
          {previewableVersions.length > 1 && (
            <VersionPicker
              previewableVersions={previewableVersions}
              selectedVersion={selectedVersion}
              protoVersionId={protoVersionId}
              show={showVersionPicker}
              onToggle={() => setShowVersionPicker(!showVersionPicker)}
              onSelect={(id) => { setProtoVersionId(id); setShowVersionPicker(false); }}
            />
          )}
          {/* 预览按钮 */}
          <PreviewButton
            hasPrototype={hasPrototype}
            totalPages={protoStatus?.total_pages || 0}
            onClick={handlePreview}
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="animate-fade-in">
          {s.activeTab === 'todos' && (
            <TodosTab
              projectId={s.id!}
              versions={s.versions}
              versionTodos={s.versionTodos}
              expandedVersions={s.expandedVersions}
              toggleVersion={s.toggleVersion}
              versionForm={{
                show: s.showNewVersion,
                setShow: s.setShowNewVersion,
                name: s.versionName,
                setName: s.setVersionName,
                goal: s.versionGoal,
                setGoal: s.setVersionGoal,
                type: s.versionType,
                setType: s.setVersionType,
                create: s.handleCreateVersion,
              }}
              versionActions={{
                activate: s.handleActivateVersion,
                release: s.handleReleaseVersion,
                remove: s.handleDeleteVersion,
                analyze: s.handleAnalyzeVersion,
                setCreateForVersion: s.setCreateForVersion,
              }}
              todoActions={{
                delete: s.handleDeleteTodo,
                resume: s.handleResumeTodo,
                complete: s.handleCompleteTodo,
                reopen: s.handleReopenTodo,
              }}
              navigate={s.navigate}
              onRefreshData={s.fetchData}
              onPreviewRoadmap={(session) => s.setDrawerSession(session)}
              processConstraint={s.form.process_constraint}
              getTaskState={s.getTaskState}
              onBatchStart={s.batchStart}
              canWrite={s.canWrite}
            />
          )}

          {s.activeTab === 'experiences' && (
            <ExperiencesTab
              experiences={s.experiences}
              loading={s.expLoading}
              filter={s.expFilter}
              setFilter={s.setExpFilter}
              categoryFilter={s.expCategoryFilter}
              setCategoryFilter={s.setExpCategoryFilter}
              onConfirm={s.handleConfirmExp}
              onArchive={s.handleArchiveExp}
              onPromote={s.handlePromoteExp}
              onDistill={s.handleDistillExp}
              onExtract={s.handleExtractExperiences}
              extracting={s.extracting}
            />
          )}

          {s.activeTab === 'domain_model' && (
            <DomainModelTab
              projectId={s.id}
              domainModel={s.domainModel}
              loading={s.domainModelLoading}
              review={s.domainModelReview}
              baasStatus={s.baasStatus}
              onRefresh={s.handleRefreshDomainModel}
              refreshing={s.refreshingDM}
              onExtractFromCode={s.handleExtractDomainModelFromCode}
              extractingFromCode={s.extractingDMFromCode}
              hasLocalPath={!!s.form.local_path}
            />
          )}

          {s.activeTab === 'settings' && (
            <SettingsTab
              projectId={s.id!}
              form={s.form}
              setForm={s.setForm}
              dirty={s.dirty}
              onSave={s.handleSave}
              onRefresh={() => s.fetchData({ silent: true })}
              insights={s.insights}
              onAppendConvention={s.handleAppendConvention}
              githubConnected={s.project?.github_connected}
              githubRepo={s.project?.github_repo}
              scanStatus={s.project?.scan_status}
              scanProgressText={s.project?.scan_progress}
              scanErrorText={s.project?.scan_error}
            />
          )}
        </div>
      </div>

      <CreateTodoModal
        open={!!s.createForVersion}
        onClose={() => s.setCreateForVersion(null)}
        onCreate={s.handleCreateTodo}
        projectId={s.id!}
        versionId={s.createForVersion || ''}
        versionName={s.versions.find((v) => v.id === s.createForVersion)?.name}
      />

      {(s.analyzing || s.analysisResult) && (
        <AnalysisModal
          analyzing={s.analyzing}
          analysisResult={s.analysisResult}
          analysisCached={s.analysisCached}
          analysisSuggestions={s.analysisSuggestions}
          existingTodoTitles={new Set(
            Object.values(s.versionTodos).flat().map((t) => t.title)
          )}
          onClose={s.closeAnalysis}
          onCreateTodos={async (items) => {
            for (const item of items) {
              await s.createTodoFromSuggestion({
                title: item.action,
                description: `[${item.priority}] 来源：AI 迭代分析建议\n\n背景：${item.reason}\n\n该需求由 AI 分析当前版本状态后推荐，可直接推进执行。`,
                priority: item.priority === 'P0' ? 1 : item.priority === 'P1' ? 2 : 3,
              });
            }
            s.fetchData({ silent: true });
          }}
        />
      )}

      {s.drawerSession && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/40" onClick={() => s.setDrawerSession(null)} />
          <div className="relative h-full">
            <DeliverableDrawer
              onClose={() => s.setDrawerSession(null)}
              content={{ type: 'roadmap', data: s.drawerSession }}
              width={roadmapDrawerWidth}
              onWidthChange={setRoadmapDrawerWidth}
            />
          </div>
        </div>
      )}
    </div>
  );
}
