import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Todo } from '../types/api';

/**
 * 需求 CRUD 操作：创建、删除、恢复、完成、重开。
 */
export function useTodoActions(
  projectId: string | undefined,
  navigate: (path: string) => void,
  toast: (msg: string, type?: string) => void,
  versionTodos: Record<string, Todo[]>,
  setVersionTodos: React.Dispatch<React.SetStateAction<Record<string, Todo[]>>>,
  fetchData: (opts?: { silent?: boolean }) => Promise<void>,
  versions: Array<{ id: string; status: string }>,
) {
  const [createForVersion, setCreateForVersion] = useState<string | null>(null);
  const [completeConfirm, setCompleteConfirm] = useState<{ todoId: string; hasDeliverables: boolean } | null>(null);

  const handleCreateTodo = async (title: string, description: string, priority?: number) => {
    if (!projectId || !createForVersion) return;
    try {
      const todo = await api.createTodo({ title, description, project_id: projectId, version_id: createForVersion, priority });
      setVersionTodos((prev) => ({
        ...prev,
        [createForVersion]: [todo, ...(prev[createForVersion] || [])],
      }));
      api.extractTags(todo.id).then((updated) => {
        setVersionTodos((prev) => ({
          ...prev,
          [createForVersion]: (prev[createForVersion] || []).map((t) => (t.id === updated.id ? updated : t)),
        }));
      }).catch((err) => { console.warn('Failed to extract tags:', err); });
      navigate(`/todo/${todo.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) return;
      toast('创建需求失败', 'error');
    }
  };

  const createTodoFromSuggestion = async (data: { title: string; description: string; priority: number }) => {
    if (!projectId) return;
    const targetVersion = versions.find((v) => v.status === 'planning') || versions.find((v) => v.status === 'active');
    if (!targetVersion) {
      toast('没有可用的版本来承接新需求', 'error');
      return;
    }
    const existingTodos = versionTodos[targetVersion.id] || [];
    if (existingTodos.some((t) => t.title === data.title)) {
      toast('该需求已存在，跳过重复创建', 'warning');
      return;
    }
    try {
      await api.createTodo({
        title: data.title,
        description: data.description,
        project_id: projectId,
        version_id: targetVersion.id,
        priority: data.priority,
      });
    } catch {
      toast('创建需求失败', 'error');
    }
  };

  const handleDeleteTodo = async (todoId: string, todoTitle: string, versionId: string) => {
    if (!window.confirm(`确定删除需求「${todoTitle}」？此操作不可撤销。`)) return;
    try {
      await api.deleteTodo(todoId);
      setVersionTodos((prev) => ({
        ...prev,
        [versionId]: (prev[versionId] || []).filter((t) => t.id !== todoId),
      }));
      fetchData({ silent: true });
      toast('需求已删除', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '删除失败';
      toast(msg, 'error');
    }
  };

  const handleResumeTodo = async (todoId: string) => {
    if (!projectId) return;
    try {
      await api.resumeSuspendedTodo(projectId, todoId);
      fetchData({ silent: true });
      toast('需求已恢复', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '恢复失败';
      toast(msg, 'error');
    }
  };

  const handleCompleteTodo = async (todoId: string) => {
    let hasDeliverables = false;
    try {
      const tracker = await api.getDeliverables(todoId);
      const produced = Object.values(tracker.deliverables || {}).filter(
        (s) => s === 'produced' || s === 'confirmed'
      );
      hasDeliverables = produced.length > 0;
    } catch { /* tracker 不存在视为无交付物 */ }
    setCompleteConfirm({ todoId, hasDeliverables });
  };

  const confirmCompleteTodo = async () => {
    if (!completeConfirm) return;
    try {
      await api.completeTodo(completeConfirm.todoId);
      fetchData({ silent: true });
      toast('需求已完成', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '操作失败';
      toast(msg, 'error');
    } finally {
      setCompleteConfirm(null);
    }
  };

  const handleReopenTodo = async (todoId: string) => {
    try {
      await api.reopenTodo(todoId);
      fetchData({ silent: true });
      toast('需求已恢复为进行中', 'success');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : '操作失败';
      toast(msg, 'error');
    }
  };

  return {
    createForVersion, setCreateForVersion,
    handleCreateTodo, createTodoFromSuggestion,
    handleDeleteTodo, handleResumeTodo,
    handleCompleteTodo, handleReopenTodo,
    completeConfirm, setCompleteConfirm, confirmCompleteTodo,
  };
}
