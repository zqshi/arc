import type {
  Todo,
  CreateTodoRequest,
  UpdateTodoRequest,
  Conversation,
  Message,
  Experience,
  PipelineState,
  PipelinePhase,
  Artifact,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

class ApiClient {
  private base: string;

  constructor(base: string) {
    this.base = base;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const resp = await fetch(`${this.base}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    });

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

  // ─── Todos ──────────────────────────────────────────────

  async listTodos(status?: string): Promise<Todo[]> {
    const params = status ? `?status=${encodeURIComponent(status)}` : '';
    const data = await this.request<{ items: Todo[]; total: number }>(`/api/todos${params}`);
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

  async listExperiences(): Promise<Experience[]> {
    const data = await this.request<{ items: Experience[]; total: number }>('/api/experiences');
    return data.items;
  }

  async getExperience(id: string): Promise<Experience> {
    return this.request<Experience>(`/api/experiences/${id}`);
  }

  async searchExperiences(query: string): Promise<Experience[]> {
    const data = await this.request<{ items: Experience[]; total: number }>(
      `/api/experiences/search?q=${encodeURIComponent(query)}`,
    );
    return data.items;
  }
}

export { ApiError };
export const api = new ApiClient(API_BASE);
