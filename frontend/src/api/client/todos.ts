import type {
  Todo,
  CreateTodoRequest,
  UpdateTodoRequest,
  PipelineState,
  PipelinePhase,
  Artifact,
  DeliverableTracker,
} from '../../types/api';
import type { RequestFn } from './base';

export function createTodoMethods(request: RequestFn) {
  return {
    listTodos: async (params?: { status?: string; project_id?: string; version_id?: string }): Promise<Todo[]> => {
      const sp = new URLSearchParams();
      if (params?.status) sp.set('status', params.status);
      if (params?.project_id) sp.set('project_id', params.project_id);
      if (params?.version_id) sp.set('version_id', params.version_id);
      const qs = sp.toString();
      const data = await request<{ items: Todo[]; total: number }>(`/api/todos${qs ? `?${qs}` : ''}`);
      return data.items;
    },

    getTodo: (id: string): Promise<Todo> =>
      request(`/api/todos/${id}`),

    createTodo: (data: CreateTodoRequest): Promise<Todo> =>
      request('/api/todos', { method: 'POST', body: JSON.stringify(data) }),

    updateTodo: (id: string, data: UpdateTodoRequest): Promise<Todo> =>
      request(`/api/todos/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

    deleteTodo: (id: string): Promise<void> =>
      request(`/api/todos/${id}`, { method: 'DELETE' }),

    addDependency: (todoId: string, dependsOnId: string): Promise<void> =>
      request(`/api/todos/${todoId}/dependencies`, { method: 'POST', body: JSON.stringify({ depends_on_id: dependsOnId }) }),

    removeDependency: (todoId: string, dependsOnId: string): Promise<void> =>
      request(`/api/todos/${todoId}/dependencies/${dependsOnId}`, { method: 'DELETE' }),

    extractTags: (id: string): Promise<Todo> =>
      request(`/api/todos/${id}/extract-tags`, { method: 'POST' }),

    startConversation: (todoId: string): Promise<Todo> =>
      request(`/api/todos/${todoId}/start-conversation`, { method: 'POST' }),

    getDeliverables: (todoId: string): Promise<DeliverableTracker> =>
      request(`/api/todos/${todoId}/deliverables`),

    getPipeline: (todoId: string): Promise<PipelineState> =>
      request(`/api/todos/${todoId}/pipeline`),

    startPipeline: (todoId: string): Promise<PipelinePhase[]> =>
      request(`/api/todos/${todoId}/pipeline/start`, { method: 'POST' }),

    startPhase: (todoId: string, phaseType: string): Promise<PipelinePhase> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/start`, { method: 'POST' }),

    generateArtifact: (todoId: string, phaseType: string): Promise<Artifact> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/generate`, { method: 'POST' }),

    confirmPhase: (todoId: string, phaseType: string): Promise<PipelinePhase> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/confirm`, { method: 'POST' }),

    skipPhase: (todoId: string, phaseType: string): Promise<PipelinePhase> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/skip`, { method: 'POST' }),

    rollbackPipeline: (todoId: string, targetPhase: string): Promise<PipelinePhase> =>
      request(`/api/todos/${todoId}/pipeline/rollback`, { method: 'POST', body: JSON.stringify({ target_phase: targetPhase }) }),

    listArtifacts: (todoId: string): Promise<Artifact[]> =>
      request(`/api/todos/${todoId}/artifacts`),

    getArtifact: (todoId: string, artifactId: string): Promise<Artifact> =>
      request(`/api/todos/${todoId}/artifacts/${artifactId}`),

    updateArtifact: (todoId: string, artifactId: string, content: Record<string, unknown>): Promise<Artifact> =>
      request(`/api/todos/${todoId}/artifacts/${artifactId}`, { method: 'PATCH', body: JSON.stringify({ content }) }),

    confirmArtifact: (todoId: string, artifactId: string): Promise<Artifact> =>
      request(`/api/todos/${todoId}/artifacts/${artifactId}/confirm`, { method: 'POST' }),

    publishArtifact: (todoId: string, artifactId: string): Promise<{ preview_url: string }> =>
      request(`/api/todos/${todoId}/artifacts/${artifactId}/publish`, { method: 'POST' }),

    unpublishArtifact: (todoId: string, artifactId: string): Promise<void> =>
      request(`/api/todos/${todoId}/artifacts/${artifactId}/publish`, { method: 'DELETE' }),

    confirmPush: (todoId: string, message?: string, branch?: string): Promise<{
      success: boolean; commit_sha: string; branch: string; remote_url: string; files_changed: number;
    }> =>
      request(`/api/todos/${todoId}/confirm-push`, {
        method: 'POST',
        body: JSON.stringify({ message, branch }),
        headers: { 'Content-Type': 'application/json' },
      }),
  };
}
