import { useState, useEffect, useCallback } from 'react';
import { Building2, Plus, Users, LogIn, Crown, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import type { Organization, OrgMember, OrgPlan } from '../types/api';

const PLAN_LABELS: Record<string, string> = { free: '免费版', pro: '专业版', team: '团队版' };
const ROLE_LABELS: Record<string, string> = { admin: '管理员', member: '成员' };
const PLANS: OrgPlan[] = ['free', 'pro', 'team'];

export default function Organizations() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', slug: '' });
  const [members, setMembers] = useState<OrgMember[] | null>(null);
  const [membersOrg, setMembersOrg] = useState<Organization | null>(null);
  const [inviteUserId, setInviteUserId] = useState('');

  const fetchOrgs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setOrgs(await api.listOrgs());
    } catch {
      setError('加载组织列表失败');
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOrgs(); }, [fetchOrgs]);

  const handleCreate = async () => {
    if (!createForm.name.trim()) return;
    try {
      await api.createOrg({ name: createForm.name.trim(), slug: createForm.slug.trim() || undefined });
      setShowCreate(false);
      setCreateForm({ name: '', slug: '' });
      fetchOrgs();
    } catch {
      setError('创建失败, slug 可能已存在 (仅小写字母/数字/连字符)');
    }
  };

  const handleSwitch = async (orgId: string) => {
    try {
      const res = await api.switchOrg(orgId);
      localStorage.setItem('access_token', res.access_token);
      window.location.reload();
    } catch {
      setError('切换组织失败, 确认你是该组织成员');
    }
  };

  const openMembers = async (org: Organization) => {
    setMembersOrg(org);
    setMembers([]);
    try {
      setMembers(await api.listOrgMembers(org.id));
    } catch {
      setMembers(null);
    }
  };

  const handleInvite = async () => {
    if (!membersOrg || !inviteUserId.trim()) return;
    try {
      await api.inviteOrgMember(membersOrg.id, inviteUserId.trim());
      setInviteUserId('');
      setMembers(await api.listOrgMembers(membersOrg.id));
    } catch {
      setError('邀请失败, 确认用户 ID 有效');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!membersOrg) return;
    try {
      await api.removeOrgMember(membersOrg.id, userId);
      setMembers(await api.listOrgMembers(membersOrg.id));
    } catch {
      setError('移除成员失败, 需管理员权限');
    }
  };

  const handleUpdatePlan = async (orgId: string, plan: OrgPlan) => {
    try {
      await api.updateOrgPlan(orgId, plan);
      fetchOrgs();
    } catch {
      setError('更新套餐失败, 需管理员权限');
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-semibold">组织管理</h1>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" /> 创建组织
        </button>
      </div>

      {error && <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="text-text-muted">加载中…</div>
      ) : orgs.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center text-text-muted">
          你还未加入任何组织, 点击「创建组织」开始
        </div>
      ) : (
        <div className="space-y-3">
          {orgs.map((org) => (
            <div key={org.id} className="rounded-lg border border-border bg-bg-card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{org.name}</span>
                    {org.role === 'admin' && <Crown className="h-4 w-4 text-amber-500" />}
                    <span className="rounded bg-bg-muted px-2 py-0.5 text-xs">{PLAN_LABELS[org.plan] || org.plan}</span>
                    <span className="text-xs text-text-muted">/{org.slug}</span>
                  </div>
                  <div className="mt-1 text-xs text-text-muted">你的角色: {ROLE_LABELS[org.role] || org.role}</div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => openMembers(org)} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-bg-muted">
                    <Users className="h-3 w-3" /> 成员
                  </button>
                  <button onClick={() => handleSwitch(org.id)} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-bg-muted">
                    <LogIn className="h-3 w-3" /> 切换
                  </button>
                </div>
              </div>
              {org.role === 'admin' && (
                <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
                  <span className="text-xs text-text-muted">套餐:</span>
                  {PLANS.map((p) => (
                    <button key={p} onClick={() => handleUpdatePlan(org.id, p)} className={`rounded px-2 py-0.5 text-xs ${org.plan === p ? 'bg-primary text-white' : 'border border-border hover:bg-bg-muted'}`}>
                      {PLAN_LABELS[p]}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCreate(false)}>
          <div className="w-96 rounded-lg bg-bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">创建组织</h2>
            <label className="mb-3 block">
              <span className="text-sm text-text-muted">名称</span>
              <input value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} className="mt-1 w-full rounded border border-border px-2 py-1.5" placeholder="我的组织" />
            </label>
            <label className="mb-4 block">
              <span className="text-sm text-text-muted">Slug (可选, 小写字母/数字/连字符)</span>
              <input value={createForm.slug} onChange={(e) => setCreateForm({ ...createForm, slug: e.target.value })} className="mt-1 w-full rounded border border-border px-2 py-1.5" placeholder="my-org" />
            </label>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="rounded border border-border px-3 py-1.5 text-sm">取消</button>
              <button onClick={handleCreate} className="rounded bg-primary px-3 py-1.5 text-sm text-white">创建</button>
            </div>
          </div>
        </div>
      )}

      {membersOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => { setMembersOrg(null); setMembers(null); }}>
          <div className="w-96 rounded-lg bg-bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">{membersOrg.name} - 成员</h2>
            {members === null ? (
              <div className="text-sm text-text-muted">加载失败或无权限</div>
            ) : (
              <div className="space-y-2">
                {members.map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded border border-border px-2 py-1.5">
                    <div>
                      <div className="text-sm">{m.display_name}</div>
                      <div className="text-xs text-text-muted">{ROLE_LABELS[m.role] || m.role}</div>
                    </div>
                    {membersOrg.role === 'admin' && m.user_id !== membersOrg.id && (
                      <button onClick={() => handleRemoveMember(m.user_id)} className="text-red-500 hover:text-red-700">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {membersOrg.role === 'admin' && (
              <div className="mt-4 flex gap-2 border-t border-border pt-4">
                <input value={inviteUserId} onChange={(e) => setInviteUserId(e.target.value)} placeholder="用户 ID" className="flex-1 rounded border border-border px-2 py-1.5 text-sm" />
                <button onClick={handleInvite} className="rounded bg-primary px-3 py-1.5 text-sm text-white">邀请</button>
              </div>
            )}
            <button onClick={() => { setMembersOrg(null); setMembers(null); }} className="mt-4 w-full rounded border border-border py-1.5 text-sm">关闭</button>
          </div>
        </div>
      )}
    </div>
  );
}
