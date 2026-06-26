import type { Capability, CapabilityCreate, CapabilityUpdate, PhaseCapabilities } from '../../types/api';
import type { RequestFn } from './base';

/**
 * 能力管理 API client (v6.8.0)。
 * 读 (list/get) 登录即可; 写 (create/update/delete) 需 admin (后端守卫)。
 * updatePhaseCapabilities 为项目环节级能力配置 (admin only, 单 phase 增量)。
 */
export function createCapabilityMethods(request: RequestFn) {
  return {
    listCapabilities: (params?: {
      type?: string;
      status?: string;
      scope?: string;
      skip?: number;
      limit?: number;
    }): Promise<Capability[]> => {
      const query = new URLSearchParams();
      if (params?.type) query.set('type', params.type);
      if (params?.status) query.set('status', params.status);
      if (params?.scope) query.set('scope', params.scope);
      if (params?.skip !== undefined) query.set('skip', String(params.skip));
      if (params?.limit !== undefined) query.set('limit', String(params.limit));
      const qs = query.toString();
      return request(`/api/capabilities${qs ? `?${qs}` : ''}`);
    },

    getCapability: (id: string): Promise<Capability> =>
      request(`/api/capabilities/${id}`),

    createCapability: (data: CapabilityCreate): Promise<Capability> =>
      request('/api/capabilities', { method: 'POST', body: JSON.stringify(data) }),

    updateCapability: (id: string, data: CapabilityUpdate): Promise<Capability> =>
      request(`/api/capabilities/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

    deleteCapability: (id: string): Promise<{ status: string; id: string }> =>
      request(`/api/capabilities/${id}`, { method: 'DELETE' }),

    updatePhaseCapabilities: (
      projectId: string,
      phase: string,
      capabilityIds: string[],
    ): Promise<{ phase_capabilities: PhaseCapabilities }> =>
      request(`/api/projects/${projectId}/pipeline/phase-capabilities`, {
        method: 'PUT',
        body: JSON.stringify({ phase, capability_ids: capabilityIds }),
      }),
  };
}
