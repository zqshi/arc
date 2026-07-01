import { useState } from 'react';
import { Plus, GitBranch, Map } from 'lucide-react';
import type { Version, Todo, PlanningSession, ProcessConstraint } from '../../types/api';
import { ProjectPlanningPanel } from './ProjectPlanningPanel';
import { VersionCreateForm, type VersionForm, type VersionActions, type TodoActions } from './todos-tab-parts';
import { VersionRow } from './version-row-parts';
import type { TaskState } from '../../hooks/useProjectTaskStream';

interface TodosTabProps {
  projectId: string;
  versions: Version[];
  versionTodos: Record<string, Todo[]>;
  expandedVersions: Set<string>;
  toggleVersion: (id: string) => void;
  versionForm: VersionForm;
  versionActions: VersionActions;
  todoActions: TodoActions;
  navigate: (path: string) => void;
  onRefreshData: () => void;
  onPreviewRoadmap?: (session: PlanningSession) => void;
  getTaskState?: (todoId: string) => TaskState;
  onBatchStart?: (todoIds: string[]) => Promise<void>;
  processConstraint?: ProcessConstraint;
  canWrite?: boolean;
}

export function TodosTab({
  projectId,
  versions,
  versionTodos,
  expandedVersions,
  toggleVersion,
  versionForm,
  versionActions,
  todoActions,
  navigate,
  onRefreshData,
  onPreviewRoadmap,
  getTaskState,
  onBatchStart,
  processConstraint,
  canWrite = true,
}: TodosTabProps) {
  const [showGlobalPlanning, setShowGlobalPlanning] = useState(false);
  const [batchStarting, setBatchStarting] = useState(false);
  const isConversationMode = processConstraint !== 'strict';

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <GitBranch size={13} /> 版本 & 需求
        </h2>
        <div className="flex items-center gap-2">
          {canWrite && (
            <>
              <button
                onClick={() => setShowGlobalPlanning(!showGlobalPlanning)}
                className={`flex items-center gap-1 rounded-md border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  showGlobalPlanning
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-text-secondary hover:text-text-primary'
                }`}
              >
                <Map size={12} /> AI 全局规划
              </button>
              <button
                onClick={() => versionForm.setShow(true)}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary"
              >
                <Plus size={12} /> 新版本
              </button>
            </>
          )}
        </div>
      </div>

      {/* Global Planning Panel */}
      {showGlobalPlanning && (
        <ProjectPlanningPanel
          projectId={projectId}
          onRoadmapApplied={() => { setShowGlobalPlanning(false); onRefreshData(); }}
          onClose={() => setShowGlobalPlanning(false)}
          onPreviewRoadmap={onPreviewRoadmap}
        />
      )}

      {versionForm.show && <VersionCreateForm form={versionForm} />}

      <div className="space-y-3">
        {versions.length === 0 && !versionForm.show && !showGlobalPlanning && (
          <p className="rounded-lg border border-border bg-bg-card p-4 text-center text-xs text-text-muted">
            还没有版本。创建一个版本来圈定需求范围，或使用「AI 全局规划」从文档自动生成。
          </p>
        )}
        {versions.map((v) => (
          <VersionRow
            key={v.id}
            v={v}
            isExpanded={expandedVersions.has(v.id)}
            todos={versionTodos[v.id] || []}
            toggleVersion={toggleVersion}
            projectId={projectId}
            navigate={navigate}
            onRefreshData={onRefreshData}
            onPreviewRoadmap={onPreviewRoadmap}
            versionActions={versionActions}
            todoActions={todoActions}
            canWrite={canWrite}
            isConversationMode={isConversationMode}
            getTaskState={getTaskState}
            onBatchStart={onBatchStart}
            batchStarting={batchStarting}
            setBatchStarting={setBatchStarting}
          />
        ))}
      </div>
    </section>
  );
}
