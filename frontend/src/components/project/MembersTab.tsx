import { useState, useEffect, useCallback } from 'react';
import { Users, UserPlus, Trash2, Shield, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import type { ProjectMember, UserRole } from '../../types/api';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../Toast';

interface Props {
  projectId: string;
}

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  member: '成员',
  viewer: '观察者',
};

const ROLE_COLORS: Record<UserRole, string> = {
  admin: 'bg-purple-100 text-purple-700',
  member: 'bg-blue-100 text-blue-700',
  viewer: 'bg-gray-100 text-gray-600',
};

export function MembersTab({ projectId }: Props) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteUserId, setInviteUserId] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('member');
  const [inviting, setInviting] = useState(false);

  const fetchMembers = useCallback(async () => {
    try {
      const data = await api.listMembers(projectId);
      setMembers(data);
    } catch {
      toast('加载成员列表失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [projectId, toast]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const handleInvite = async () => {
    if (!inviteUserId.trim()) return;
    setInviting(true);
    try {
      await api.addMember(projectId, inviteUserId.trim(), inviteRole);
      toast('成员已添加', 'success');
      setInviteUserId('');
      await fetchMembers();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '添加失败';
      toast(msg, 'error');
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: UserRole) => {
    try {
      await api.updateMemberRole(projectId, userId, newRole);
      toast('角色已更新', 'success');
      await fetchMembers();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '更新失败';
      toast(msg, 'error');
    }
  };

  const handleRemove = async (userId: string, displayName: string) => {
    if (!confirm(`确定要移除成员「${displayName}」吗？`)) return;
    try {
      await api.removeMember(projectId, userId);
      toast('成员已移除', 'success');
      await fetchMembers();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '移除失败';
      toast(msg, 'error');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 邀请成员 */}
      <div className="bg-white rounded-lg border p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
          <UserPlus className="w-4 h-4" />
          添加成员
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="输入用户 ID"
            value={inviteUserId}
            onChange={e => setInviteUserId(e.target.value)}
            className="flex-1 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={inviteRole}
            onChange={e => setInviteRole(e.target.value as UserRole)}
            className="px-3 py-2 border rounded-md text-sm bg-white"
          >
            <option value="member">成员</option>
            <option value="viewer">观察者</option>
            <option value="admin">管理员</option>
          </select>
          <button
            onClick={handleInvite}
            disabled={inviting || !inviteUserId.trim()}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          >
            {inviting && <Loader2 className="w-3 h-3 animate-spin" />}
            添加
          </button>
        </div>
      </div>

      {/* 成员列表 */}
      <div className="bg-white rounded-lg border">
        <div className="px-4 py-3 border-b">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Users className="w-4 h-4" />
            项目成员 ({members.length})
          </h3>
        </div>
        <div className="divide-y">
          {members.map(m => (
            <div key={m.user_id} className="px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm font-medium text-gray-600">
                  {m.display_name.charAt(0)}
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-900">
                    {m.display_name}
                    {m.user_id === user?.id && (
                      <span className="ml-1 text-xs text-gray-400">(我)</span>
                    )}
                  </div>
                  {m.username && (
                    <div className="text-xs text-gray-500">@{m.username}</div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {m.user_id !== user?.id ? (
                  <>
                    <select
                      value={m.role}
                      onChange={e => handleRoleChange(m.user_id, e.target.value as UserRole)}
                      className="px-2 py-1 border rounded text-xs bg-white"
                    >
                      <option value="admin">管理员</option>
                      <option value="member">成员</option>
                      <option value="viewer">观察者</option>
                    </select>
                    <button
                      onClick={() => handleRemove(m.user_id, m.display_name)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                      title="移除成员"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                ) : (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[m.role]}`}>
                    <Shield className="w-3 h-3 inline mr-1" />
                    {ROLE_LABELS[m.role]}
                  </span>
                )}
              </div>
            </div>
          ))}
          {members.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-gray-400">
              暂无成员
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
