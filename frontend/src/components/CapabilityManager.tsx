import { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, Loader2, Bot, BookOpen, Plug } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from './Toast';
import { useConfirm } from './ConfirmProvider';
import { useAuth } from '../contexts/AuthContext';
import { CapabilityEditorModal } from './CapabilityEditorModal';
import type { Capability, CapabilityType } from '../types/api';

const TYPE_ICON: Record<CapabilityType, typeof Bot> = {
  agent: Bot,
  skill: BookOpen,
  mcp: Plug,
};
const TYPE_LABEL: Record<CapabilityType, string> = { agent: 'Agent', skill: 'Skill', mcp: 'MCP' };

export function CapabilityManager() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [loading, setLoading] = useState(true);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Capability | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listCapabilities();
      setCapabilities(list);
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : '加载能力失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditing(null); setEditorOpen(true); };
  const openEdit = (cap: Capability) => { setEditing(cap); setEditorOpen(true); };

  const handleSaved = (cap: Capability) => {
    setCapabilities((prev) => {
      const idx = prev.findIndex((c) => c.id === cap.id);
      if (idx >= 0) { const next = [...prev]; next[idx] = cap; return next; }
      return [cap, ...prev];
    });
  };

  const toggleStatus = async (cap: Capability) => {
    const nextStatus = cap.status === 'active' ? 'disabled' : 'active';
    const snapshot = capabilities;
    setTogglingId(cap.id);
    setCapabilities((p) => p.map((c) => (c.id === cap.id ? { ...c, status: nextStatus } : c)));
    try {
      await api.updateCapability(cap.id, { status: nextStatus });
      toast(`已${nextStatus === 'active' ? '启用' : '禁用'}`, 'success');
    } catch (err) {
      setCapabilities(snapshot);
      toast(err instanceof ApiError ? err.detail : '操作失败', 'error');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (cap: Capability) => {
    const ok = await confirm({
      title: '删除能力',
      message: `确定删除「${cap.name}」吗？已配置该能力的环节将不再注入。`,
      confirmLabel: '删除',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await api.deleteCapability(cap.id);
      setCapabilities((p) => p.filter((c) => c.id !== cap.id));
      toast('能力已删除', 'success');
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : '删除失败', 'error');
    }
  };

  // D2: 分组后副标题显示配置摘要 (skill→source, agent→agent_key), 提升信息密度
  const subInfo = (cap: Capability): string => {
    const cfg = (cap.config ?? {}) as Record<string, unknown>;
    if (cap.type === 'skill') return cfg.source === 'inline' ? '内联文本' : '目录来源';
    if (cap.type === 'agent' && typeof cfg.agent_key === 'string' && cfg.agent_key) {
      return String(cfg.agent_key);
    }
    return cap.scope;
  };

  return (
    <section className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <Plug size={13} /> 能力管理
        </h2>
        {isAdmin && (
          <button onClick={openCreate} className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white hover:bg-accent-hover">
            <Plus size={12} /> 新增能力
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8 text-text-muted">
          <Loader2 size={16} className="animate-spin" />
        </div>
      ) : capabilities.length === 0 ? (
        <p className="py-8 text-center text-[11px] text-text-muted">
          暂无能力声明。{isAdmin ? '点击「新增能力」创建。' : ''}
        </p>
      ) : (
        <div className="space-y-4">
          {(['agent', 'skill', 'mcp'] as CapabilityType[]).map((t) => {
            const items = capabilities.filter((c) => c.type === t);
            if (items.length === 0) return null;
            return (
              <div key={t}>
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                  {TYPE_LABEL[t]} <span className="font-normal opacity-70">· {items.length}</span>
                </p>
                <div className="space-y-2">
                  {items.map((cap) => {
                    const Icon = TYPE_ICON[cap.type] ?? Plug;
                    const isActive = cap.status === 'active';
                    return (
                      <div key={cap.id} className="flex items-center gap-3 rounded-md border border-border/60 px-3 py-2">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-md ${isActive ? 'bg-accent/10 text-accent' : 'bg-bg-elevated text-text-muted'}`}>
                          <Icon size={13} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium text-text-primary">{cap.name}</p>
                          <p className="truncate text-[10px] text-text-muted">{subInfo(cap)}</p>
                        </div>
                        {isAdmin && (
                          <>
                            <button
                              onClick={() => toggleStatus(cap)}
                              disabled={togglingId === cap.id}
                              className={`relative h-5 w-9 flex-shrink-0 rounded-full transition-colors ${isActive ? 'bg-accent' : 'bg-border'} disabled:opacity-50`}
                              title={isActive ? '点击禁用' : '点击启用'}
                              aria-label={isActive ? '禁用能力' : '启用能力'}
                            >
                              <span className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${isActive ? 'translate-x-4' : ''}`} />
                            </button>
                            <button onClick={() => openEdit(cap)} className="rounded p-1 text-text-muted hover:bg-bg-elevated hover:text-text-secondary" aria-label="编辑能力">
                              <Pencil size={12} />
                            </button>
                            <button onClick={() => handleDelete(cap)} className="rounded p-1 text-text-muted hover:bg-bg-elevated hover:text-status-error" aria-label="删除能力">
                              <Trash2 size={12} />
                            </button>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <CapabilityEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        onSaved={handleSaved}
        capability={editing}
      />
    </section>
  );
}
