import type {
  LLMProvider,
  ProviderTemplate,
  VerifyResult,
  ListModelsResult,
} from '../../types/api';
import type { RequestFn } from './base';

export function createLLMMethods(request: RequestFn) {
  return {
    listProviderTemplates: (): Promise<ProviderTemplate[]> =>
      request('/api/llm/providers/templates'),

    listProviders: (skip = 0, limit = 50): Promise<LLMProvider[]> =>
      request(`/api/llm/providers?skip=${skip}&limit=${limit}`),

    createProvider: (data: {
      name: string;
      kind: 'openai_compatible' | 'anthropic';
      base_url: string;
      api_key: string;
      is_default?: boolean;
    }): Promise<LLMProvider> =>
      request('/api/llm/providers', { method: 'POST', body: JSON.stringify(data) }),

    updateProvider: (
      id: string,
      data: {
        name?: string;
        base_url?: string;
        api_key?: string;
        is_default?: boolean;
      },
    ): Promise<LLMProvider> =>
      request(`/api/llm/providers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

    deleteProvider: (id: string): Promise<{ status: string }> =>
      request(`/api/llm/providers/${id}`, { method: 'DELETE' }),

    verifyCredentials: (data: {
      kind: 'openai_compatible' | 'anthropic';
      base_url: string;
      api_key: string;
      name?: string;
    }): Promise<VerifyResult> =>
      request('/api/llm/providers/verify', { method: 'POST', body: JSON.stringify(data) }),

    listModels: (id: string, refresh = false): Promise<ListModelsResult> =>
      request(`/api/llm/providers/${id}/models${refresh ? '?refresh=true' : ''}`),
  };
}
