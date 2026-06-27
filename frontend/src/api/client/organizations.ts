import type {
  Organization,
  OrgDetail,
  OrgMember,
  CreateOrgRequest,
  OrgPlan,
  SwitchOrgResult,
  OrgRole,
} from '../../types/api';
import type { RequestFn } from './base';

/** 组织管理 API (v6.11, 对齐 backend interface/routes/organization.py, 前缀 /api/orgs)。 */
export function createOrganizationMethods(request: RequestFn) {
  return {
    listOrgs: (): Promise<Organization[]> => request('/api/orgs'),

    createOrg: (data: CreateOrgRequest): Promise<OrgDetail> =>
      request('/api/orgs', { method: 'POST', body: JSON.stringify(data) }),

    getOrg: (orgId: string): Promise<OrgDetail> => request(`/api/orgs/${orgId}`),

    listOrgMembers: (orgId: string): Promise<OrgMember[]> =>
      request(`/api/orgs/${orgId}/members`),

    inviteOrgMember: (orgId: string, userId: string, role: OrgRole = 'member'): Promise<OrgMember> =>
      request(`/api/orgs/${orgId}/members`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, role }),
      }),

    removeOrgMember: (orgId: string, userId: string): Promise<void> =>
      request(`/api/orgs/${orgId}/members/${userId}`, { method: 'DELETE' }),

    updateOrgPlan: (orgId: string, plan: OrgPlan): Promise<OrgDetail> =>
      request(`/api/orgs/${orgId}/plan`, { method: 'PUT', body: JSON.stringify({ plan }) }),

    switchOrg: (orgId: string): Promise<SwitchOrgResult> =>
      request('/api/orgs/switch', { method: 'POST', body: JSON.stringify({ org_id: orgId }) }),
  };
}
