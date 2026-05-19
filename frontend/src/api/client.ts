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
  Version,
  CreateVersionRequest,
  SystemSettings,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || '';

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

class ApiClient {
  private base: string;

  constructor(base: string) {
    this.base = base;
  }

  private async request<T>(path: string, options?: RequestInit, retried = false): Promise<T> {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (options?.headers) {
      Object.assign(headers, options.headers);
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const resp = await fetch(`${this.base}${path}`, {
      ...options,
      headers,
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

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ detail: resp.statusText }));
      const detail = typeof error.detail === 'string'
        ? error.detail
        : JSON.stringify(error.detail);
      throw new ApiError(resp.status, detail || resp.statusText);
    }

    if (resp.status === 204) return undefined as T;
    return resp.json();
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

  async extractTags(id: string): Promise<Todo> {
    return this.request<Todo>(`/api/todos/${id}/extract-tags`, { method: 'POST' });
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

  async feedbackExperience(id: string, todoId: string, helpful: boolean): Promise<void> {
    return this.request<void>(`/api/experiences/${id}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ todo_id: todoId, helpful }),
    });
  }

  async listProjectExperiences(projectId: string, status?: string): Promise<Experience[]> {
    const sp = new URLSearchParams();
    if (status) sp.set('status', status);
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

  // ─── Settings ──────────────────────────────────────────

  async getSettings(): Promise<SystemSettings> {
    return this.request<SystemSettings>('/api/settings');
  }
}

export { ApiError };
export const api = new ApiClient(API_BASE);
