import type {
  AgentSession,
  AgentEvent,
  AvailableAgentsResponse,
  ConflictAnalysis,
  PlanningDocument,
  PlanningSession,
  ScopeDiff,
} from '../../types/api';
import type { RequestFn } from './base';

export function createAgentMethods(request: RequestFn) {
  return {
    executeAgent: (todoId: string, phaseType: string, agentType?: string): Promise<AgentSession> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/execute`, { method: 'POST', body: JSON.stringify({ agent_type: agentType || null }) }),

    getAgentSession: (todoId: string, phaseType: string): Promise<AgentSession | null> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/agent-session`),

    cancelAgent: (todoId: string, phaseType: string): Promise<AgentSession> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/cancel-agent`, { method: 'POST' }),

    getAgentEvents: (todoId: string, phaseType: string): Promise<AgentEvent[]> =>
      request(`/api/todos/${todoId}/phases/${phaseType}/agent-events`),

    getAvailableAgents: (): Promise<AvailableAgentsResponse> =>
      request('/api/todos/agent-types'),
  };
}

export function createPlanningMethods(request: RequestFn) {
  return {
    uploadDocument: (projectId: string, file: File): Promise<PlanningDocument> => {
      const formData = new FormData();
      formData.append('file', file);
      return request(`/api/projects/${projectId}/documents`, { method: 'POST', body: formData, headers: {} });
    },

    listDocuments: (projectId: string): Promise<PlanningDocument[]> =>
      request(`/api/projects/${projectId}/documents`),

    deleteDocument: (projectId: string, docId: string): Promise<void> =>
      request(`/api/projects/${projectId}/documents/${docId}`, { method: 'DELETE' }),

    createPlanningSession: (projectId: string, data: { document_ids?: string[]; constraints?: Record<string, unknown>; version_id?: string }): Promise<PlanningSession> =>
      request(`/api/projects/${projectId}/planning-sessions`, { method: 'POST', body: JSON.stringify(data) }),

    listPlanningSessions: (projectId: string): Promise<PlanningSession[]> =>
      request(`/api/projects/${projectId}/planning-sessions`),

    listVersionPlanningSessions: (projectId: string, versionId: string): Promise<PlanningSession[]> =>
      request(`/api/projects/${projectId}/versions/${versionId}/planning-sessions`),

    generateRoadmap: (projectId: string, sessionId: string): Promise<PlanningSession> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/generate`, { method: 'POST' }),

    confirmRoadmap: (projectId: string, sessionId: string): Promise<PlanningSession> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/confirm`, { method: 'POST' }),

    applyRoadmap: (projectId: string, sessionId: string): Promise<{ message: string; version_ids: string[] }> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/apply`, { method: 'POST' }),

    previewApplyDiff: (projectId: string, sessionId: string): Promise<ScopeDiff> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/preview-diff`, { method: 'POST' }),

    applyWithDiff: (projectId: string, sessionId: string, abandonTodoIds: string[]): Promise<{ message: string; created_count: number; abandoned_count: number }> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/apply-with-diff`, { method: 'POST', body: JSON.stringify({ abandon_todo_ids: abandonTodoIds }) }),

    revisePlanningSession: (projectId: string, sessionId: string): Promise<PlanningSession> =>
      request(`/api/projects/${projectId}/planning-sessions/${sessionId}/revise`, { method: 'POST' }),

    analyzeIteration: (projectId: string, versionId: string): Promise<{ analysis: string; cached: boolean }> =>
      request(`/api/projects/${projectId}/versions/${versionId}/analyze`, { method: 'POST' }),

    detectConflicts: (projectId: string, versionId: string): Promise<ConflictAnalysis> =>
      request(`/api/projects/${projectId}/versions/${versionId}/detect-conflicts`, { method: 'POST' }),
  };
}
