import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { VersionType } from '../types/api';
import type { ToastType } from '../components/Toast';
import type { ConfirmOptions } from '../components/ConfirmProvider';

/**
 * 版本 CRUD 操作：创建、激活、发布、删除。
 */
export function useVersionActions(
  projectId: string | undefined,
  toast: (msg: string, type?: ToastType) => void,
  refreshVersions: () => Promise<void>,
  confirm?: (options: ConfirmOptions) => Promise<boolean>,
) {
  const [showNewVersion, setShowNewVersion] = useState(false);
  const [versionName, setVersionName] = useState('');
  const [versionGoal, setVersionGoal] = useState('');
  const [versionType, setVersionType] = useState<VersionType>('minor');

  const handleCreateVersion = async () => {
    if (!projectId) return;
    try {
      await api.createVersion(projectId, {
        name: versionName.trim() || undefined,
        goal: versionGoal.trim(),
        version_type: versionType,
      });
      setShowNewVersion(false);
      setVersionName('');
      setVersionGoal('');
      setVersionType('minor');
      await refreshVersions();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '创建版本失败';
      toast(msg, 'error');
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    if (!projectId) return;
    try {
      await api.activateVersion(projectId, versionId);
      await refreshVersions();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '激活版本失败';
      toast(msg, 'error');
    }
  };

  const handleReleaseVersion = async (versionId: string) => {
    if (!projectId) return;
    try {
      await api.releaseVersion(projectId, versionId);
      await refreshVersions();
      toast('版本已发布', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '发布版本失败';
      toast(msg, 'error');
    }
  };

  const handleDeleteVersion = async (versionId: string, name: string) => {
    if (!projectId) return;
    const ok = confirm
      ? await confirm({ title: '删除版本', message: `确定删除版本「${name}」？此操作不可撤销。`, confirmLabel: '删除', variant: 'danger' })
      : window.confirm(`确定删除版本「${name}」？此操作不可撤销。`);
    if (!ok) return;
    try {
      await api.deleteVersion(projectId, versionId);
      await refreshVersions();
      toast('版本已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  return {
    showNewVersion, setShowNewVersion,
    versionName, setVersionName,
    versionGoal, setVersionGoal,
    versionType, setVersionType,
    handleCreateVersion, handleActivateVersion, handleReleaseVersion, handleDeleteVersion,
  };
}
