import type {
  Conversation,
  Message,
  Experience,
  UpdateExperienceRequest,
} from '../../types/api';
import type { RequestFn } from './base';

export function createConversationMethods(request: RequestFn) {
  return {
    listConversations: async (todoId: string): Promise<Conversation[]> => {
      const data = await request<{ items: Conversation[] }>(`/api/todos/${todoId}/conversations`);
      return data.items;
    },

    getConversation: (id: string): Promise<Conversation> =>
      request(`/api/conversations/${id}`),

    sendMessage: (conversationId: string, content: string): Promise<Message> =>
      request(`/api/conversations/${conversationId}/messages`, { method: 'POST', body: JSON.stringify({ content }) }),
  };
}

export function createExperienceMethods(request: RequestFn) {
  return {
    listExperiences: async (params?: { project_id?: string; status?: string; scope?: string }): Promise<Experience[]> => {
      const sp = new URLSearchParams();
      if (params?.project_id) sp.set('project_id', params.project_id);
      if (params?.status) sp.set('status', params.status);
      if (params?.scope) sp.set('scope', params.scope);
      const qs = sp.toString();
      const data = await request<{ items: Experience[]; total: number }>(`/api/experiences${qs ? `?${qs}` : ''}`);
      return data.items;
    },

    getExperience: (id: string): Promise<Experience> =>
      request(`/api/experiences/${id}`),

    searchExperiences: async (query: string, projectId?: string): Promise<Experience[]> => {
      const sp = new URLSearchParams({ q: query });
      if (projectId) sp.set('project_id', projectId);
      const data = await request<{ items: Experience[]; total: number }>(`/api/experiences/search?${sp.toString()}`);
      return data.items;
    },

    updateExperience: (id: string, data: UpdateExperienceRequest): Promise<Experience> =>
      request(`/api/experiences/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

    confirmExperience: (id: string): Promise<Experience> =>
      request(`/api/experiences/${id}/confirm`, { method: 'POST' }),

    archiveExperience: (id: string): Promise<Experience> =>
      request(`/api/experiences/${id}/archive`, { method: 'POST' }),

    promoteExperience: (id: string): Promise<Experience> =>
      request(`/api/experiences/${id}/promote`, { method: 'POST' }),

    distillExperience: (id: string): Promise<Experience> =>
      request(`/api/experiences/${id}/distill`, { method: 'POST' }),

    getReuseAnalytics: (projectId?: string): Promise<{ by_category: Array<{ category: string; count: number; total_reuse: number }>; top_reused: Experience[]; stale_count: number }> => {
      const sp = new URLSearchParams();
      if (projectId) sp.set('project_id', projectId);
      const qs = sp.toString();
      return request(`/api/experiences/analytics/reuse${qs ? `?${qs}` : ''}`);
    },

    feedbackExperience: (id: string, todoId: string, helpful: boolean): Promise<void> =>
      request(`/api/experiences/${id}/feedback`, { method: 'POST', body: JSON.stringify({ todo_id: todoId, helpful }) }),

    listProjectExperiences: async (projectId: string, params?: { status?: string; category?: string }): Promise<Experience[]> => {
      const sp = new URLSearchParams();
      if (params?.status) sp.set('status', params.status);
      if (params?.category) sp.set('category', params.category);
      const qs = sp.toString();
      const data = await request<{ items: Experience[]; total: number }>(`/api/projects/${projectId}/experiences${qs ? `?${qs}` : ''}`);
      return data.items;
    },

    getProjectExperienceInsights: (projectId: string): Promise<{ suggestions: Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }> }> =>
      request(`/api/projects/${projectId}/experience-insights`),
  };
}
