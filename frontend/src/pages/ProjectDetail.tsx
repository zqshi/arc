import { useState } from 'react';
import { ArrowLeft, FileText, Lightbulb, Settings, Sparkles, Loader2, Database, CheckSquare, Square, Plus, Monitor } from 'lucide-react';
import ActionMenu from '../components/ActionMenu';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';
import ConfirmDialog from '../components/ConfirmDialog';
import MarkdownContent from '../components/MarkdownContent';
import DeliverableDrawer from '../components/DeliverableDrawer';
import { TodosTab, SettingsTab, ExperiencesTab, DomainModelTab } from '../components/project';
import { useProjectDetail } from '../hooks/useProjectDetail';

type TabKey = 'todos' | 'experiences' | 'domain_model' | 'settings';

interface Suggestion { priority: string; action: string; reason: string }

function SuggestionsPanel({ suggestions, onCreateTodos, existingTodoTitles }: { suggestions: Suggestion[]; onCreateTodos: (items: Suggestion[]) => Promise<void>; existingTodoTitles: Set<string> }) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<Set<number>>(new Set());

  const isAlreadyExists = (s: Suggestion) => existingTodoTitles.has(s.action);
  const isDisabled = (i: number) => isAlreadyExists(suggestions[i]) || created.has(i);

  const toggle = (i: number) => {
    if (isDisabled(i)) return;
    const next = new Set(selected);
    if (next.has(i)) next.delete(i); else next.add(i);
    setSelected(next);
  };

  const handleCreate = async () => {
    if (selected.size === 0) return;
    setCreating(true);
    try {
      await onCreateTodos(suggestions.filter((_, i) => selected.has(i)));
      setCreated((prev) => new Set([...prev, ...selected]));
      setSelected(new Set());
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mt-4 rounded-lg border border-accent/20 bg-accent/5 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-text-primary">行动建议</span>
        <button
          onClick={handleCreate}
          disabled={selected.size === 0 || creating}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[10px] font-medium text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          {creating ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
          创建为需求 ({selected.size})
        </button>
      </div>
      <div className="space-y-1.5">
        {suggestions.map((s, i) => {
          const disabled = isDisabled(i);
          return (
          <button
            key={i}
            onClick={() => toggle(i)}
            disabled={disabled}
            className={`flex w-full items-start gap-2 rounded-md border px-3 py-2 text-left transition-colors ${
              disabled ? 'opacity-50 cursor-not-allowed border-transparent'
              : selected.has(i) ? 'border-accent/40 bg-accent/10' : 'border-transparent hover:bg-bg-elevated/50'
            }`}
          >
            {disabled
              ? <CheckSquare size={13} className="mt-0.5 flex-shrink-0 text-status-done" />
              : selected.has(i) ? <CheckSquare size={13} className="mt-0.5 flex-shrink-0 text-accent" /> : <Square size={13} className="mt-0.5 flex-shrink-0 text-text-muted" />
            }
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className={`rounded px-1 py-0.5 text-[9px] font-bold ${
                  s.priority === 'P0' ? 'bg-status-error/15 text-status-error' : s.priority === 'P1' ? 'bg-amber-500/15 text-amber-600' : 'bg-text-muted/10 text-text-muted'
                }`}>{s.priority}</span>
                <span className="text-xs font-medium text-text-primary">{s.action}</span>
                {disabled && <span className="text-[9px] text-status-done">已添加</span>}
              </div>
              {s.reason && <p className="mt-0.5 text-[11px] text-text-muted">{s.reason}</p>}
            </div>
          </button>
          );
        })}
      </div>
    </div>
  );
}

const TAB_ITEMS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: 'todos', label: '需求', icon: FileText },
  { key: 'experiences', label: '经验', icon: Lightbulb },
  { key: 'domain_model', label: '领域模型', icon: Database },
  { key: 'settings', label: '设置', icon: Settings },
];

export default function ProjectDetail() {
  const s = useProjectDetail();
  const [roadmapDrawerWidth, setRoadmapDrawerWidth] = useState(560);

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

        <button
          onClick={() => {
            const token = localStorage.getItem('access_token') || '';
            window.open(`${import.meta.env.VITE_API_URL || ''}/api/projects/${s.id}/prototype-preview?token=${encodeURIComponent(token)}`, '_blank');
          }}
          className="ml-auto flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-text-muted hover:border-accent hover:text-accent transition-colors"
          title="在新标签页预览项目原型"
        >
          <Monitor size={13} /> 预览原型
        </button>
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

      {/* Complete todo confirmation */}
      <ConfirmDialog
        open={!!s.completeConfirm}
        title={s.completeConfirm?.hasDeliverables ? '标记需求完成' : '确认完成'}
        message={
          s.completeConfirm?.hasDeliverables
            ? '确定将该需求标记为已完成？'
            : '该需求尚未产出任何交付物，确定标记为已完成？后续可通过「恢复」按钮撤销。'
        }
        variant={s.completeConfirm?.hasDeliverables ? 'default' : 'warning'}
        confirmLabel="标记完成"
        onConfirm={s.confirmCompleteTodo}
        onCancel={() => s.setCompleteConfirm(null)}
      />
    </div>
  );
}
