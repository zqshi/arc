import type { RequestFn } from './base';

export interface DomainTemplate {
  id: string;
  title: string;
  description: string;
  category: string;
  source_project_id: string | null;
  source_version_id: string | null;
  source_user_id: string;
  schema_template: Record<string, unknown>;
  entity_patterns: string[];
  state_machine_patterns: string[];
  permission_patterns: string[];
  tags: string[];
  status: 'draft' | 'confirmed' | 'published' | 'deprecated';
  scope: 'personal' | 'organization' | 'public';
  usage_count: number;
  success_count: number;
  success_rate: number;
  confidence: number;
  created_at: string | null;
  last_used_at: string | null;
}

export interface TemplateUpdateRequest {
  title?: string;
  description?: string;
  category?: string;
  tags?: string[];
}

export interface TemplateApplyRequest {
  template_id: string;
  project_id: string;
  requirement: string;
  model_version?: number;
  supabase_url?: string;
}

export function createTemplateMethods(request: RequestFn) {
  return {
    listTemplates: (skip = 0, limit = 20): Promise<{ items: DomainTemplate[]; skip: number; limit: number } | DomainTemplate[]> =>
      request(`/api/templates?skip=${skip}&limit=${limit}`),

    getTemplate: (id: string): Promise<DomainTemplate> =>
      request(`/api/templates/${id}`),

    updateTemplate: (id: string, body: TemplateUpdateRequest): Promise<DomainTemplate> =>
      request(`/api/templates/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

    confirmTemplate: (id: string): Promise<DomainTemplate> =>
      request(`/api/templates/${id}/confirm`, { method: 'POST' }),

    publishTemplate: (id: string): Promise<DomainTemplate> =>
      request(`/api/templates/${id}/publish`, { method: 'POST' }),

    deprecateTemplate: (id: string): Promise<DomainTemplate> =>
      request(`/api/templates/${id}/deprecate`, { method: 'POST' }),

    searchTemplates: (query: string, limit = 5): Promise<DomainTemplate[]> =>
      request(`/api/templates/search`, {
        method: 'POST',
        body: JSON.stringify({ query, limit }),
      }),

    applyTemplate: (body: TemplateApplyRequest): Promise<{ status: string; template_id: string }> =>
      request(`/api/templates/apply`, { method: 'POST', body: JSON.stringify(body) }),
  };
}
