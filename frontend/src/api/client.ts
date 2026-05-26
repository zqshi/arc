import type {
  Todo,
  CreateTodoRequest,
  UpdateTodoRequest,
  Conversation,
  Message,
  Experience,
  UpdateExperienceRequest,
  PipelineState,
  PipelinePhase,
  Artifact,
  AgentSession,
  AgentEvent,
  AvailableAgentsResponse,
  Project,
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectMember,
  Version,
  CreateVersionRequest,
  SystemSettings,
  PlanningDocument,
  PlanningSession,
  DeliverableTracker,
  DomainModel,
  DomainModelValidation,
  ScopeDiff,
  BatchStartResult,
  QuickMessageResponse,
  TaskStreamEvent,
  UsageResponse,
  PlanLimitsResponse,
} from '../types/api';
import { quotaEvents } from '../lib/quota-events';

const API_BASE = import.meta.env.VITE_API_URL || '';

export interface ScanEvent {
  event: string;
  message?: string;
  content?: string;
  summary?: string;
  detail?: string;
}

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) return refreshPromise;

  isRefreshing = true;
  refreshPromise = (async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    try {
      const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!resp.ok) return false;

      const data = await resp.json();
      localStorage.setItem('access_token', data.access_token);
      return true;
    } catch {
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function isTokenExpiringSoon(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp as number;
    return exp * 1000 - Date.now() < 120_000;
  } catch {
    return false;
  }
}

class ApiClient {
  private base: string;

  constructor(base: string) {
    this.base = base;
  }

  private async request<T>(path: string, options?: RequestInit, retried = false): Promise<T> {
    let token = localStorage.getItem('access_token');

    if (token && !retried && isTokenExpiringSoon(token)) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        token = localStorage.getItem('access_token');
      }
    }

    const isFormData = options?.body instanceof FormData;
    const headers: Record<string, string> = isFormData ? {} : { 'Content-Type': 'application/json' };
    if (options?.headers && !(isFormData && Object.keys(options.headers).length === 0)) {
      Object.assign(headers, options.headers);
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30_000);

    try {
      const resp = await fetch(`${this.base}${path}`, {
        ...options,
        headers,
        signal: options?.signal || controller.signal,
      });

      if (resp.status === 401 && !retried) {
        const refreshed = await tryRefreshToken();
        if (refreshed) {
          return this.request(path, options, true);
        }
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/login';
        throw new ApiError(401, '登录已过期');
      }

      if (resp.status === 403) {
        const error = await resp.json().catch(() => ({ detail: resp.statusText }));
        const detail = typeof error.detail === 'string'
          ? error.detail
          : JSON.stringify(error.detail);
        if (detail.includes('套餐') || detail.includes('上限')) {
          quotaEvents.emit(detail);
        }
        throw new ApiError(403, detail || '无权限');
      }

      if (!resp.ok) {
        const error = await resp.json().catch(() => ({ detail: resp.statusText }));
        const detail = typeof error.detail === 'string'
          ? error.detail
          : JSON.stringify(error.detail);
        throw new ApiError(resp.status, detail || resp.statusText);
      }

      if (resp.status === 204) return undefined as T;
      return resp.json();
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiError(0, 'Request aborted');
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // ─── Projects ────────────────────────────────────────────

  async listProjects(): Promise<Project[]> {
    return this.request<Project[]>('/api/projects');
  }

  async getProject(id: string): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`);
  }

  async createProject(data: CreateProjectRequest): Promise<Project> {
    return this.request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateProject(id: string, data: UpdateProjectRequest): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async archiveProject(id: string): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}/archive`, { method: 'POST' });
  }

  async deleteProject(id: string): Promise<void> {
    return this.request<void>(`/api/projects/${id}`, { method: 'DELETE' });
  }

  async connectGitHub(projectId: string, token: string): Promise<{ status: string; repo: string; webhook_url: string; webhook_secret: string }> {
    return this.request(`/api/projects/${projectId}/github/connect`, {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  }

  async disconnectGitHub(projectId: string): Promise<void> {
    return this.request(`/api/projects/${projectId}/github/disconnect`, { method: 'DELETE' });
  }

  async syncGitHubIssues(projectId: string): Promise<{ synced: number; created: number; updated: number }> {
    return this.request(`/api/projects/${projectId}/github/sync`, { method: 'POST' });
  }

  async getDomainModel(projectId: string): Promise<DomainModel> {
    return this.request<DomainModel>(`/api/projects/${projectId}/domain-model`);
  }

  async refreshDomainModel(projectId: string): Promise<{ merged: number; domain_model: DomainModel }> {
    return this.request(`/api/projects/${projectId}/domain-model/refresh`, { method: 'POST' });
  }

  async validateDomainModel(projectId: string): Promise<DomainModelValidation> {
    return this.request(`/api/projects/${projectId}/domain-model/validate`, { method: 'POST' });
  }

  async extractProjectExperiences(projectId: string, versionId?: string): Promise<{ extracted: number; skipped: number; failed: number }> {
    const qs = versionId ? `?version_id=${versionId}` : '';
    return this.request(`/api/projects/${projectId}/extract-experiences${qs}`, { method: 'POST' });
  }

  async updateDomainModel(projectId: string, data: DomainModel): Promise<DomainModel> {
    return this.request<DomainModel>(`/api/projects/${projectId}/domain-model`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // ─── Project Members ──────────────────────────────────

  async listMembers(projectId: string): Promise<ProjectMember[]> {
    return this.request<ProjectMember[]>(`/api/projects/${projectId}/members`);
  }

  async addMember(projectId: string, userId: string, role: string = 'member'): Promise<ProjectMember> {
    return this.request<ProjectMember>(`/api/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, role }),
    });
  }

  async updateMemberRole(projectId: string, userId: string, role: string): Promise<ProjectMember> {
    return this.request<ProjectMember>(`/api/projects/${projectId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    });
  }

  async removeMember(projectId: string, userId: string): Promise<void> {
    return this.request<void>(`/api/projects/${projectId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // ─── Versions ──────────────────────────────────────────

  async listVersions(projectId: string): Promise<Version[]> {
    return this.request<Version[]>(`/api/projects/${projectId}/versions`);
  }

  async createVersion(projectId: string, data: CreateVersionRequest): Promise<Version> {
    return this.request<Version>(`/api/projects/${projectId}/versions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async activateVersion(projectId: string, versionId: string): Promise<Version> {
    return this.request<Version>(`/api/projects/${projectId}/versions/${versionId}/activate`, {
      method: 'POST',
    });
  }

  async releaseVersion(projectId: string, versionId: string): Promise<Version> {
    return this.request<Version>(`/api/projects/${projectId}/versions/${versionId}/release`, {
      method: 'POST',
    });
  }

  async deleteVersion(projectId: string, versionId: string): Promise<void> {
    return this.request<void>(`/api/projects/${projectId}/versions/${versionId}`, {
      method: 'DELETE',
    });
  }

  // ─── Todos ──────────────────────────────────────────────

  async listTodos(params?: { status?: string; project_id?: string; version_id?: string }): Promise<Todo[]> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    if (params?.version_id) searchParams.set('version_id', params.version_id);
    const qs = searchParams.toString();
    const data = await this.request<{ items: Todo[]; total: number }>(`/api/todos${qs ? `?${qs}` : ''}`);
    return data.items;
  }

  async getTodo(id: string): Promise<Todo> {
    return this.request<Todo>(`/api/todos/${id}`);
  }

  async createTodo(data: CreateTodoRequest): Promise<Todo> {
    return this.request<Todo>('/api/todos', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTodo(id: string, data: UpdateTodoRequest): Promise<Todo> {
    return this.request<Todo>(`/api/todos/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteTodo(id: string): Promise<void> {
    return this.request<void>(`/api/todos/${id}`, { method: 'DELETE' });
  }

  async addDependency(todoId: string, dependsOnId: string): Promise<void> {
    return this.request(`/api/todos/${todoId}/dependencies`, {
      method: 'POST',
      body: JSON.stringify({ depends_on_id: dependsOnId }),
    });
  }

  async removeDependency(todoId: string, dependsOnId: string): Promise<void> {
    return this.request(`/api/todos/${todoId}/dependencies/${dependsOnId}`, { method: 'DELETE' });
  }

  async extractTags(id: string): Promise<Todo> {
    return this.request<Todo>(`/api/todos/${id}/extract-tags`, { method: 'POST' });
  }

  async startConversation(todoId: string): Promise<Todo> {
    return this.request<Todo>(`/api/todos/${todoId}/start-conversation`, { method: 'POST' });
  }

  async getDeliverables(todoId: string): Promise<DeliverableTracker> {
    return this.request<DeliverableTracker>(`/api/todos/${todoId}/deliverables`);
  }

  // ─── Pipeline ───────────────────────────────────────────

  async getPipeline(todoId: string): Promise<PipelineState> {
    return this.request<PipelineState>(`/api/todos/${todoId}/pipeline`);
  }

  async startPipeline(todoId: string): Promise<PipelinePhase[]> {
    return this.request<PipelinePhase[]>(`/api/todos/${todoId}/pipeline/start`, {
      method: 'POST',
    });
  }

  async startPhase(todoId: string, phaseType: string): Promise<PipelinePhase> {
    return this.request<PipelinePhase>(`/api/todos/${todoId}/phases/${phaseType}/start`, {
      method: 'POST',
    });
  }

  async generateArtifact(todoId: string, phaseType: string): Promise<Artifact> {
    return this.request<Artifact>(`/api/todos/${todoId}/phases/${phaseType}/generate`, {
      method: 'POST',
    });
  }

  async confirmPhase(todoId: string, phaseType: string): Promise<PipelinePhase> {
    return this.request<PipelinePhase>(`/api/todos/${todoId}/phases/${phaseType}/confirm`, {
      method: 'POST',
    });
  }

  async skipPhase(todoId: string, phaseType: string): Promise<PipelinePhase> {
    return this.request<PipelinePhase>(`/api/todos/${todoId}/phases/${phaseType}/skip`, {
      method: 'POST',
    });
  }

  async rollbackPipeline(todoId: string, targetPhase: string): Promise<PipelinePhase> {
    return this.request<PipelinePhase>(`/api/todos/${todoId}/pipeline/rollback`, {
      method: 'POST',
      body: JSON.stringify({ target_phase: targetPhase }),
    });
  }

  // ─── Artifacts ──────────────────────────────────────────

  async listArtifacts(todoId: string): Promise<Artifact[]> {
    return this.request<Artifact[]>(`/api/todos/${todoId}/artifacts`);
  }

  async getArtifact(todoId: string, artifactId: string): Promise<Artifact> {
    return this.request<Artifact>(`/api/todos/${todoId}/artifacts/${artifactId}`);
  }

  async updateArtifact(todoId: string, artifactId: string, content: Record<string, unknown>): Promise<Artifact> {
    return this.request<Artifact>(`/api/todos/${todoId}/artifacts/${artifactId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
  }

  async confirmArtifact(todoId: string, artifactId: string): Promise<Artifact> {
    return this.request<Artifact>(`/api/todos/${todoId}/artifacts/${artifactId}/confirm`, {
      method: 'POST',
    });
  }

  async publishArtifact(todoId: string, artifactId: string): Promise<{ preview_url: string }> {
    return this.request<{ preview_url: string }>(`/api/todos/${todoId}/artifacts/${artifactId}/publish`, {
      method: 'POST',
    });
  }

  async unpublishArtifact(todoId: string, artifactId: string): Promise<void> {
    await this.request<void>(`/api/todos/${todoId}/artifacts/${artifactId}/unpublish`, {
      method: 'POST',
    });
  }

  // ─── Conversations ─────────────────────────────────────

  async listConversations(todoId: string): Promise<Conversation[]> {
    const data = await this.request<{ items: Conversation[]; total: number }>(
      `/api/todos/${todoId}/conversations`,
    );
    return data.items;
  }

  async getConversation(id: string): Promise<Conversation> {
    return this.request<Conversation>(`/api/conversations/${id}`);
  }

  async sendMessage(conversationId: string, content: string): Promise<Message> {
    return this.request<Message>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  // ─── Experiences ────────────────────────────────────────

  async listExperiences(params?: { project_id?: string; status?: string; scope?: string }): Promise<Experience[]> {
    const sp = new URLSearchParams();
    if (params?.project_id) sp.set('project_id', params.project_id);
    if (params?.status) sp.set('status', params.status);
    if (params?.scope) sp.set('scope', params.scope);
    const qs = sp.toString();
    const data = await this.request<{ items: Experience[]; total: number }>(`/api/experiences${qs ? `?${qs}` : ''}`);
    return data.items;
  }

  async getExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}`);
  }

  async searchExperiences(query: string, projectId?: string): Promise<Experience[]> {
    const sp = new URLSearchParams({ q: query });
    if (projectId) sp.set('project_id', projectId);
    const data = await this.request<{ items: Experience[]; total: number }>(
      `/api/experiences/search?${sp.toString()}`,
    );
    return data.items;
  }

  async updateExperience(id: string, data: UpdateExperienceRequest): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async confirmExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}/confirm`, { method: 'POST' });
  }

  async archiveExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}/archive`, { method: 'POST' });
  }

  async promoteExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}/promote`, { method: 'POST' });
  }

  async distillExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}/distill`, { method: 'POST' });
  }

  async getReuseAnalytics(projectId?: string): Promise<{ by_category: Array<{ category: string; count: number; total_reuse: number }>; top_reused: Experience[]; stale_count: number }> {
    const sp = new URLSearchParams();
    if (projectId) sp.set('project_id', projectId);
    const qs = sp.toString();
    return this.request(`/api/experiences/analytics/reuse${qs ? `?${qs}` : ''}`);
  }

  async feedbackExperience(id: string, todoId: string, helpful: boolean): Promise<void> {
    return this.request<void>(`/api/experiences/${id}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ todo_id: todoId, helpful }),
    });
  }

  async listProjectExperiences(projectId: string, params?: { status?: string; category?: string }): Promise<Experience[]> {
    const sp = new URLSearchParams();
    if (params?.status) sp.set('status', params.status);
    if (params?.category) sp.set('category', params.category);
    const qs = sp.toString();
    const data = await this.request<{ items: Experience[]; total: number }>(
      `/api/projects/${projectId}/experiences${qs ? `?${qs}` : ''}`,
    );
    return data.items;
  }

  async getProjectExperienceInsights(projectId: string): Promise<{ suggestions: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }> }> {
    return this.request(`/api/projects/${projectId}/experience-insights`);
  }

  // ─── Agent ──────────────────────────────────────────────

  async executeAgent(todoId: string, phaseType: string, agentType?: string): Promise<AgentSession> {
    return this.request<AgentSession>(`/api/todos/${todoId}/phases/${phaseType}/execute`, {
      method: 'POST',
      body: JSON.stringify({ agent_type: agentType || null }),
    });
  }

  async getAgentSession(todoId: string, phaseType: string): Promise<AgentSession | null> {
    return this.request<AgentSession | null>(`/api/todos/${todoId}/phases/${phaseType}/agent-session`);
  }

  async cancelAgent(todoId: string, phaseType: string): Promise<AgentSession> {
    return this.request<AgentSession>(`/api/todos/${todoId}/phases/${phaseType}/cancel-agent`, {
      method: 'POST',
    });
  }

  async getAgentEvents(todoId: string, phaseType: string): Promise<AgentEvent[]> {
    return this.request<AgentEvent[]>(`/api/todos/${todoId}/phases/${phaseType}/agent-events`);
  }

  async getAvailableAgents(): Promise<AvailableAgentsResponse> {
    return this.request<AvailableAgentsResponse>('/api/todos/agent-types');
  }

  // ─── Planning ─────────────────────────────────────────

  async uploadDocument(projectId: string, file: File): Promise<PlanningDocument> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<PlanningDocument>(`/api/projects/${projectId}/documents`, {
      method: 'POST',
      body: formData,
      headers: {},
    });
  }

  async listDocuments(projectId: string): Promise<PlanningDocument[]> {
    return this.request<PlanningDocument[]>(`/api/projects/${projectId}/documents`);
  }

  async deleteDocument(projectId: string, docId: string): Promise<void> {
    return this.request<void>(`/api/projects/${projectId}/documents/${docId}`, { method: 'DELETE' });
  }

  async createPlanningSession(projectId: string, data: { document_ids?: string[]; constraints?: Record<string, unknown>; version_id?: string }): Promise<PlanningSession> {
    return this.request<PlanningSession>(`/api/projects/${projectId}/planning-sessions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listPlanningSessions(projectId: string): Promise<PlanningSession[]> {
    return this.request<PlanningSession[]>(`/api/projects/${projectId}/planning-sessions`);
  }

  async listVersionPlanningSessions(projectId: string, versionId: string): Promise<PlanningSession[]> {
    return this.request<PlanningSession[]>(`/api/projects/${projectId}/versions/${versionId}/planning-sessions`);
  }

  async generateRoadmap(projectId: string, sessionId: string): Promise<PlanningSession> {
    return this.request<PlanningSession>(`/api/projects/${projectId}/planning-sessions/${sessionId}/generate`, {
      method: 'POST',
    });
  }

  async confirmRoadmap(projectId: string, sessionId: string): Promise<PlanningSession> {
    return this.request<PlanningSession>(`/api/projects/${projectId}/planning-sessions/${sessionId}/confirm`, {
      method: 'POST',
    });
  }

  async applyRoadmap(projectId: string, sessionId: string): Promise<{ message: string; version_ids: string[] }> {
    return this.request(`/api/projects/${projectId}/planning-sessions/${sessionId}/apply`, {
      method: 'POST',
    });
  }

  async previewApplyDiff(projectId: string, sessionId: string): Promise<ScopeDiff> {
    return this.request<ScopeDiff>(`/api/projects/${projectId}/planning-sessions/${sessionId}/preview-diff`, {
      method: 'POST',
    });
  }

  async applyWithDiff(projectId: string, sessionId: string, abandonTodoIds: string[]): Promise<{ message: string; created_count: number; abandoned_count: number }> {
    return this.request(`/api/projects/${projectId}/planning-sessions/${sessionId}/apply-with-diff`, {
      method: 'POST',
      body: JSON.stringify({ abandon_todo_ids: abandonTodoIds }),
    });
  }

  async revisePlanningSession(projectId: string, sessionId: string): Promise<PlanningSession> {
    return this.request<PlanningSession>(`/api/projects/${projectId}/planning-sessions/${sessionId}/revise`, {
      method: 'POST',
    });
  }

  async analyzeIteration(projectId: string, versionId: string): Promise<{ analysis: string }> {
    return this.request(`/api/projects/${projectId}/versions/${versionId}/analyze`, {
      method: 'POST',
    });
  }

  async getModeSwitchImpact(projectId: string): Promise<{ active_count: number; pending_count: number; safe_to_switch: boolean }> {
    return this.request(`/api/projects/${projectId}/mode-switch-impact`);
  }

  // ─── Settings ──────────────────────────────────────────

  async getSettings(): Promise<SystemSettings> {
    return this.request<SystemSettings>('/api/settings');
  }

  // ─── Filesystem ───────────────────────────────────────

  async browseDirectory(path: string = '~'): Promise<{ current: string; parent: string | null; dirs: string[] }> {
    return this.request(`/api/filesystem/browse?path=${encodeURIComponent(path)}`);
  }

  async createDirectory(path: string): Promise<{ path: string }> {
    return this.request('/api/filesystem/mkdir', { method: 'POST', body: JSON.stringify({ path }) });
  }

  async scanCodebase(projectId: string, force = false): Promise<{ summary?: string; cached?: boolean; task_id?: string; status?: string }> {
    const params = force ? '?force=true' : '';
    return this.request(`/api/projects/${projectId}/scan-codebase${params}`, { method: 'POST' });
  }

  scanCodebaseStream(projectId: string, onEvent: (event: ScanEvent) => void, signal?: AbortSignal): void {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${this.base}/api/projects/${projectId}/scan-codebase/stream`, {
      headers,
      signal,
    }).then(async (resp) => {
      if (!resp.ok || !resp.body) {
        onEvent({ event: 'error', detail: `HTTP ${resp.status}` });
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7);
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const parsed = JSON.parse(data);
              onEvent({ event: currentEvent || parsed.event, ...parsed });
            } catch {
              // skip malformed data
            }
            currentEvent = '';
          }
        }
      }

      onEvent({ event: 'close' });
    }).catch((err) => {
      if (err.name !== 'AbortError') {
        onEvent({ event: 'error', detail: err.message || '连接失败' });
      }
    });
  }

  // ─── Task Orchestration (Conversation Mode) ───────────────

  async batchStartConversations(projectId: string, todoIds: string[]): Promise<{ results: BatchStartResult[] }> {
    return this.request(`/api/projects/${projectId}/batch-start-conversations`, {
      method: 'POST',
      body: JSON.stringify({ todo_ids: todoIds }),
    });
  }

  async sendQuickMessage(todoId: string, content: string): Promise<QuickMessageResponse> {
    return this.request(`/api/todos/${todoId}/quick-message`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  subscribeTaskStream(
    projectId: string,
    onEvent: (event: TaskStreamEvent) => void,
    signal?: AbortSignal,
  ): void {
    const token = localStorage.getItem('access_token');
    const url = `${this.base}/api/projects/${projectId}/task-stream`;
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let retries = 0;
    const maxRetries = 5;
    const baseDelay = 2000;

    const connect = () => {
      if (signal?.aborted) return;

      fetch(url, { headers, signal }).then(async (resp) => {
        if (!resp.ok || !resp.body) {
          onEvent({ event: 'error', detail: `HTTP ${resp.status}` });
          return;
        }

        retries = 0;
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = '';
        let lastActivity = Date.now();

        const heartbeatCheck = setInterval(() => {
          if (Date.now() - lastActivity > 60_000) {
            clearInterval(heartbeatCheck);
            reader.cancel();
          }
        }, 15_000);

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            lastActivity = Date.now();
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (currentEvent === 'ping') { currentEvent = ''; continue; }
                try {
                  const parsed = JSON.parse(data);
                  onEvent({ event: (currentEvent || 'connected') as TaskStreamEvent['event'], ...parsed });
                } catch {
                  // skip malformed
                }
                currentEvent = '';
              }
            }
          }
        } finally {
          clearInterval(heartbeatCheck);
        }

        if (!signal?.aborted && retries < maxRetries) {
          retries++;
          setTimeout(connect, baseDelay * retries);
        }
      }).catch((err) => {
        if (err.name === 'AbortError') return;
        onEvent({ event: 'error', detail: err.message || '连接失败' });
        if (retries < maxRetries) {
          retries++;
          setTimeout(connect, baseDelay * retries);
        }
      });
    };

    connect();
  }

  // ─── Billing ──────────────────────────────────────────

  async getUsage(): Promise<UsageResponse> {
    return this.request<UsageResponse>('/api/billing/usage');
  }

  async getPlanLimits(): Promise<PlanLimitsResponse> {
    return this.request<PlanLimitsResponse>('/api/billing/plans');
  }
}

export { ApiError };
export const api = new ApiClient(API_BASE);
