import { useState, useEffect } from 'react';
import { ArrowLeft, FileText, Lightbulb, Settings, Sparkles, Loader2, Database, Monitor, ChevronDown } from 'lucide-react';
import ActionMenu from '../components/ActionMenu';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';
import MarkdownContent from '../components/MarkdownContent';
import DeliverableDrawer from '../components/DeliverableDrawer';
import { TodosTab, SettingsTab, ExperiencesTab, DomainModelTab } from '../components/project';
import { useProjectDetail } from '../hooks/useProjectDetail';
import { api } from '../api/client';
import { SuggestionsPanel } from '../components/project/SuggestionsPanel';

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
            <div className="relative">
              <button
                onClick={() => setShowVersionPicker(!showVersionPicker)}
                className="flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-[10px] text-text-muted hover:border-accent/50 hover:text-text-secondary transition-colors"
              >
                {selectedVersion?.name || '当前版本'}
                <ChevronDown size={10} />
              </button>
              {showVersionPicker && (
                <div className="absolute right-0 top-full z-50 mt-1 min-w-[120px] rounded-md border border-border bg-bg-primary py-1 shadow-lg">
                  <button
                    onClick={() => { setProtoVersionId(null); setShowVersionPicker(false); }}
                    className={`block w-full px-3 py-1.5 text-left text-[10px] hover:bg-bg-elevated ${!protoVersionId ? 'text-accent' : 'text-text-secondary'}`}
                  >
                    自动（当前版本）
                  </button>
                  {previewableVersions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => { setProtoVersionId(v.id); setShowVersionPicker(false); }}
                      className={`block w-full px-3 py-1.5 text-left text-[10px] hover:bg-bg-elevated ${protoVersionId === v.id ? 'text-accent' : 'text-text-secondary'}`}
                    >
                      {v.name} {v.status === 'released' ? '✓' : ''}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* 预览按钮 */}
          <button
            onClick={handlePreview}
            disabled={!hasPrototype}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors ${
              hasPrototype
                ? 'border-border text-text-muted hover:border-accent hover:text-accent'
                : 'border-border/50 text-text-muted/40 cursor-not-allowed'
            }`}
            title={hasPrototype
              ? `预览原型 (${protoStatus?.total_pages || 0} 个页面)`
              : '暂无原型页面，请先完成需求设计'
            }
          >
            <Monitor size={13} /> 预览原型
            {protoStatus && hasPrototype && (
              <span className="ml-0.5 rounded bg-accent/10 px-1 py-0.5 text-[9px] text-accent">
                {protoStatus.total_pages}
              </span>
            )}
          </button>
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
              showNewVersion={s.showNewVersion}
              setShowNewVersion={s.setShowNewVersion}
              versionName={s.versionName}
              setVersionName={s.setVersionName}
              versionGoal={s.versionGoal}
              setVersionGoal={s.setVersionGoal}
              versionType={s.versionType}
              setVersionType={s.setVersionType}
              handleCreateVersion={s.handleCreateVersion}
              handleActivateVersion={s.handleActivateVersion}
              handleReleaseVersion={s.handleReleaseVersion}
              handleDeleteVersion={s.handleDeleteVersion}
              handleDeleteTodo={s.handleDeleteTodo}
              handleResumeTodo={s.handleResumeTodo}
              handleCompleteTodo={s.handleCompleteTodo}
              handleReopenTodo={s.handleReopenTodo}
              setCreateForVersion={s.setCreateForVersion}
              navigate={s.navigate}
              onAnalyzeVersion={s.handleAnalyzeVersion}
              onRefreshData={s.fetchData}
              onPreviewRoadmap={(session) => s.setDrawerSession(session)}
              executionMode={s.form.execution_mode}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={s.closeAnalysis} />
          <div className="relative mx-4 w-full max-w-3xl animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <Sparkles size={14} className="text-accent" /> AI 迭代分析
                {s.analysisCached && (
                  <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] font-normal text-text-muted">缓存</span>
                )}
              </h2>
              <button
                onClick={s.closeAnalysis}
                className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-secondary transition-colors"
              >
                ×
              </button>
            </div>
            <div className="max-h-[75vh] overflow-y-auto px-5 py-4">
              {s.analyzing ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 size={20} className="animate-spin text-accent" />
                  <span className="ml-2 text-sm text-text-muted">AI 正在分析迭代状态...</span>
                </div>
              ) : s.analysisResult ? (
                <>
                  <MarkdownContent content={s.analysisResult} />
                  {s.analysisSuggestions.length > 0 && (
                    <SuggestionsPanel
                      suggestions={s.analysisSuggestions}
                      existingTodoTitles={new Set(
                        Object.values(s.versionTodos).flat().map((t) => t.title)
                      )}
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
                </>
              ) : null}
            </div>
          </div>
        </div>
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
