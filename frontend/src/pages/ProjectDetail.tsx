import { ArrowLeft, FileText, Lightbulb, Settings, Sparkles, Loader2, Boxes } from 'lucide-react';
import ActionMenu from '../components/ActionMenu';
import { VersionListSkeleton } from '../components/Skeleton';
import CreateTodoModal from '../components/CreateTodoModal';
import MarkdownContent from '../components/MarkdownContent';
import DeliverableDrawer from '../components/DeliverableDrawer';
import { TodosTab, SettingsTab, ExperiencesTab, DomainModelTab } from '../components/project';
import { useProjectDetail } from '../hooks/useProjectDetail';

type TabKey = 'todos' | 'experiences' | 'domain_model' | 'settings';

const TAB_ITEMS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: 'todos', label: '需求', icon: FileText },
  { key: 'experiences', label: '经验', icon: Lightbulb },
  { key: 'domain_model', label: '领域模型', icon: Boxes },
  { key: 'settings', label: '设置', icon: Settings },
];

export default function ProjectDetail() {
  const s = useProjectDetail();

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
              domainModel={s.domainModel}
              loading={s.domainModelLoading}
              onRefresh={s.handleRefreshDomainModel}
              refreshing={s.refreshingDM}
              onValidate={s.handleValidateDomainModel}
              validating={s.validatingDM}
              validation={s.dmValidation}
              onCloseValidation={() => s.setDmValidation(null)}
            />
          )}

          {s.activeTab === 'settings' && (
            <SettingsTab
              projectId={s.id!}
              form={s.form}
              setForm={s.setForm}
              dirty={s.dirty}
              onSave={s.handleSave}
              onRefresh={s.fetchData}
              insights={s.insights}
              onAppendConvention={s.handleAppendConvention}
              githubConnected={s.project?.github_connected}
              githubRepo={s.project?.github_repo}
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
          <div className="relative mx-4 w-full max-w-2xl animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h2 className="flex items-center gap-2 font-heading text-sm font-semibold text-text-primary">
                <Sparkles size={14} className="text-accent" /> AI 迭代分析
              </h2>
              <button
                onClick={s.closeAnalysis}
                className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary"
              >
                ×
              </button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
              {s.analyzing ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={20} className="animate-spin text-accent" />
                  <span className="ml-2 text-sm text-text-muted">AI 正在分析迭代状态...</span>
                </div>
              ) : s.analysisResult ? (
                <MarkdownContent content={s.analysisResult} />
              ) : null}
            </div>
          </div>
        </div>
      )}

      <DeliverableDrawer
        open={!!s.drawerSession}
        onClose={() => s.setDrawerSession(null)}
        content={s.drawerSession ? { type: 'roadmap', data: s.drawerSession } : null}
      />
    </div>
  );
}
