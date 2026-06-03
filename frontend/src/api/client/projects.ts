import type {
  Project,
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectMember,
  Version,
  CreateVersionRequest,
  DomainModel,
  DomainModelValidation,
  DomainModelSnapshot,
  ReviewFeedback,
  ImpactReport,
  UpgradeResult,
} from '../../types/api';
import type { RequestFn } from './base';

export function createProjectMethods(request: RequestFn) {
  return {
    listProjects: (includeArchived = false): Promise<Project[]> =>
      request(`/api/projects${includeArchived ? '?include_archived=true' : ''}`),

    getProject: (id: string): Promise<Project> =>
      request(`/api/projects/${id}`),

    createProject: (data: CreateProjectRequest): Promise<Project> =>
      request('/api/projects', { method: 'POST', body: JSON.stringify(data) }),

    updateProject: (id: string, data: UpdateProjectRequest): Promise<Project> =>
      request(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

    archiveProject: (id: string): Promise<Project> =>
      request(`/api/projects/${id}/archive`, { method: 'POST' }),

    activateProject: (id: string): Promise<Project> =>
      request(`/api/projects/${id}/activate`, { method: 'POST' }),

    migrateWorkspace: (projectId: string, targetPath: string): Promise<Project> =>
      request(`/api/projects/${projectId}/workspace/migrate`, { method: 'POST', body: JSON.stringify({ target_path: targetPath }) }),

    deleteProject: (id: string): Promise<void> =>
      request(`/api/projects/${id}`, { method: 'DELETE' }),

    connectGitHub: (projectId: string, token: string, repoUrl?: string): Promise<{ status: string; repo: string; webhook_url: string; webhook_secret: string }> =>
      request(`/api/projects/${projectId}/github/connect`, { method: 'POST', body: JSON.stringify({ token, repo_url: repoUrl }) }),

    disconnectGitHub: (projectId: string): Promise<void> =>
      request(`/api/projects/${projectId}/github/disconnect`, { method: 'DELETE' }),

    cloneGitHubRepo: (projectId: string, path?: string): Promise<{ status: string; local_path: string; scan_started: boolean }> =>
      request(`/api/projects/${projectId}/github/clone`, { method: 'POST', body: JSON.stringify({ path: path || '' }) }),

    syncGitHubIssues: (projectId: string): Promise<{ synced: number; created: number; updated: number }> =>
      request(`/api/projects/${projectId}/github/sync`, { method: 'POST' }),

    getDomainModel: (projectId: string): Promise<DomainModel> =>
      request(`/api/projects/${projectId}/domain-model`),

    refreshDomainModel: (projectId: string): Promise<{ merged: number; domain_model: DomainModel }> =>
      request(`/api/projects/${projectId}/domain-model/refresh`, { method: 'POST' }),

    extractDomainModelFromCode: (projectId: string): Promise<{ domain_model: DomainModel }> =>
      request(`/api/projects/${projectId}/domain-model/extract-from-code`, { method: 'POST', timeout: 180_000 }),

    validateDomainModel: (projectId: string): Promise<DomainModelValidation> =>
      request(`/api/projects/${projectId}/domain-model/validate`, { method: 'POST' }),

    extractProjectExperiences: (projectId: string, versionId?: string): Promise<{ extracted: number; skipped: number; failed: number }> =>
      request(`/api/projects/${projectId}/extract-experiences${versionId ? `?version_id=${versionId}` : ''}`, { method: 'POST' }),

    updateDomainModel: (projectId: string, data: DomainModel): Promise<DomainModel> =>
      request(`/api/projects/${projectId}/domain-model`, { method: 'PUT', body: JSON.stringify(data) }),

    listMembers: (projectId: string): Promise<ProjectMember[]> =>
      request(`/api/projects/${projectId}/members`),

    addMember: (projectId: string, userId: string, role: string = 'member'): Promise<ProjectMember> =>
      request(`/api/projects/${projectId}/members`, { method: 'POST', body: JSON.stringify({ user_id: userId, role }) }),

    updateMemberRole: (projectId: string, userId: string, role: string): Promise<ProjectMember> =>
      request(`/api/projects/${projectId}/members/${userId}`, { method: 'PATCH', body: JSON.stringify({ role }) }),

    removeMember: (projectId: string, userId: string): Promise<void> =>
      request(`/api/projects/${projectId}/members/${userId}`, { method: 'DELETE' }),

    listVersions: (projectId: string): Promise<Version[]> =>
      request(`/api/projects/${projectId}/versions`),

    createVersion: (projectId: string, data: CreateVersionRequest): Promise<Version> =>
      request(`/api/projects/${projectId}/versions`, { method: 'POST', body: JSON.stringify(data) }),

    activateVersion: (projectId: string, versionId: string): Promise<Version> =>
      request(`/api/projects/${projectId}/versions/${versionId}/activate`, { method: 'POST' }),

    releaseVersion: (projectId: string, versionId: string): Promise<Version> =>
      request(`/api/projects/${projectId}/versions/${versionId}/release`, { method: 'POST' }),

    deleteVersion: (projectId: string, versionId: string): Promise<void> =>
      request(`/api/projects/${projectId}/versions/${versionId}`, { method: 'DELETE' }),

    getModeSwitchImpact: (projectId: string): Promise<{ active_count: number; pending_count: number; safe_to_switch: boolean }> =>
      request(`/api/projects/${projectId}/mode-switch-impact`),

    // ── Review Feedback (v3.0+) ────────────────────────────

    listReviewFeedbacks: (projectId: string, status?: string): Promise<ReviewFeedback[]> =>
      request(`/api/projects/${projectId}/review-feedbacks${status ? `?status=${status}` : ''}`),

    resolveReviewFeedback: (projectId: string, feedbackId: string, action: string, note = ''): Promise<ReviewFeedback> =>
      request(`/api/projects/${projectId}/review-feedbacks/${feedbackId}`, {
        method: 'PATCH',
        body: JSON.stringify({ action, note }),
      }),

    getDomainModelHistory: (projectId: string): Promise<DomainModelSnapshot[]> =>
      request(`/api/projects/${projectId}/domain-model/history`),

    rollbackDomainModel: (projectId: string, toVersion: number): Promise<{ ok: boolean; version: number }> =>
      request(`/api/projects/${projectId}/domain-model/rollback`, {
        method: 'POST',
        body: JSON.stringify({ to_version: toVersion }),
      }),

    analyzeModelImpact: (projectId: string, aggregates: string[], scope: string): Promise<ImpactReport> =>
      request(`/api/projects/${projectId}/domain-model/impact-analysis`, {
        method: 'POST',
        body: JSON.stringify({ affected_aggregates: aggregates, change_scope: scope }),
      }),

    executeModelUpgrade: (projectId: string, feedbackIds: string[], newModel: DomainModel, strategy: string): Promise<UpgradeResult> =>
      request(`/api/projects/${projectId}/domain-model/upgrade`, {
        method: 'POST',
        body: JSON.stringify({ feedback_ids: feedbackIds, new_model: newModel, strategy }),
      }),

    resumeSuspendedTodo: (projectId: string, todoId: string): Promise<{ ok: boolean; todo_id: string; status: string }> =>
      request(`/api/projects/${projectId}/todos/${todoId}/resume`, { method: 'POST' }),
  };
}
