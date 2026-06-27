import type {
  Template,
  TemplateUpdateRequest,
  TemplateApplyResult,
} from '../../types/api';
import type { RequestFn } from './base';

/** 模板市场 API (v6.11, 对齐 backend interface/routes/template.py, 前缀 /api/templates)。 */
export function createTemplateMethods(request: RequestFn) {
  return {
    listTemplates: (skip = 0, limit = 20): Promise<Template[]> =>
      request(`/api/templates?skip=${skip}&limit=${limit}`),

    getTemplate: (templateId: string): Promise<Template> =>
      request(`/api/templates/${templateId}`),

    updateTemplate: (templateId: string, data: TemplateUpdateRequest): Promise<Template> =>
      request(`/api/templates/${templateId}`, { method: 'PATCH', body: JSON.stringify(data) }),

    confirmTemplate: (templateId: string): Promise<Template> =>
      request(`/api/templates/${templateId}/confirm`, { method: 'POST' }),

    publishTemplate: (templateId: string): Promise<Template> =>
      request(`/api/templates/${templateId}/publish`, { method: 'POST' }),

    deprecateTemplate: (templateId: string): Promise<Template> =>
      request(`/api/templates/${templateId}/deprecate`, { method: 'POST' }),

    searchTemplates: (query: string, limit = 5): Promise<Template[]> =>
      request('/api/templates/search', { method: 'POST', body: JSON.stringify({ query, limit }) }),

    applyTemplate: (
      templateId: string,
      projectId: string,
      requirement: string,
      supabaseUrl = '',
      modelVersion = 1,
    ): Promise<TemplateApplyResult> =>
      request('/api/templates/apply', {
        method: 'POST',
        body: JSON.stringify({
          template_id: templateId,
          project_id: projectId,
          requirement,
          supabase_url: supabaseUrl,
          model_version: modelVersion,
        }),
      }),
  };
}
