import { useState, useCallback } from 'react';
import { Folder, FolderPlus, ChevronRight, ArrowUp, Loader2, X, CornerDownLeft } from 'lucide-react';
import { api } from '../api/client';

interface FolderPickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  initialPath?: string;
}

export default function FolderPicker({ open, onClose, onSelect, initialPath }: FolderPickerProps) {
  const [current, setCurrent] = useState('');
  const [pathInput, setPathInput] = useState('');
  const [parent, setParent] = useState<string | null>(null);
  const [dirs, setDirs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  const browse = useCallback(async (path: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await api.browseDirectory(path);
      setCurrent(data.current);
      setPathInput(data.current);
      setParent(data.parent);
      setDirs(data.dirs);
    } catch (err) {
      setError(err instanceof Error ? err.message : '路径不存在或无权限访问');
    } finally {
      setLoading(false);
    }
  }, []);

  if (open && !current && !loading) {
    browse(initialPath || '~');
  }

  const handlePathSubmit = () => {
    const trimmed = pathInput.trim();
    if (trimmed && trimmed !== current) {
      browse(trimmed);
    }
  };

  const handleCreate = async () => {
    if (!newFolderName.trim()) return;
    const target = `${current}/${newFolderName.trim()}`;
    try {
      await api.createDirectory(target);
      setNewFolderName('');
      setCreating(false);
      browse(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败');
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-lg animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="font-heading text-sm font-semibold text-text-primary">选择工作目录</h2>
          <button onClick={onClose} className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text-secondary">
            <X size={14} />
          </button>
        </div>

        <div className="px-5 py-3">
          {/* Editable path bar */}
          <div className="mb-3 flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={pathInput}
                onChange={(e) => setPathInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) handlePathSubmit(); }}
                placeholder="输入路径或粘贴，按回车跳转"
                className="h-9 w-full rounded-md border border-border bg-bg-input pl-3 pr-8 font-mono text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
              />
              <button
                onClick={handlePathSubmit}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-accent"
                title="跳转到此路径"
              >
                <CornerDownLeft size={13} />
              </button>
            </div>
          </div>

          {/* Navigation */}
          <div className="mb-2 flex items-center gap-2">
            <button
              onClick={() => parent && browse(parent)}
              disabled={!parent || loading}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary hover:text-text-primary disabled:opacity-30"
            >
              <ArrowUp size={11} /> 上级
            </button>
            <button
              onClick={() => browse('~')}
              disabled={loading}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary hover:text-text-primary disabled:opacity-30"
            >
              ~ 主目录
            </button>
            <button
              onClick={() => setCreating(true)}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary hover:text-text-primary"
            >
              <FolderPlus size={11} /> 新建
            </button>
          </div>

          {/* Create folder inline */}
          {creating && (
            <div className="mb-2 flex items-center gap-2">
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="新文件夹名称"
                className="h-8 flex-1 rounded-md border border-border bg-bg-input px-3 text-xs text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleCreate(); if (e.key === 'Escape') setCreating(false); }}
              />
              <button onClick={handleCreate} className="rounded-md bg-accent px-2.5 py-1.5 text-[11px] text-white hover:bg-accent-hover">创建</button>
              <button onClick={() => setCreating(false)} className="rounded-md border border-border px-2 py-1.5 text-[11px] text-text-muted">取消</button>
            </div>
          )}

          {/* Error */}
          {error && <p className="mb-2 text-[11px] text-status-error">{error}</p>}

          {/* Directory list */}
          <div className="max-h-60 overflow-y-auto rounded-md border border-border">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={16} className="animate-spin text-text-muted" />
              </div>
            ) : dirs.length === 0 ? (
              <p className="px-3 py-4 text-center text-[11px] text-text-muted">无子目录（可直接选择当前目录）</p>
            ) : (
              <div className="divide-y divide-border/30">
                {dirs.map((dir) => (
                  <button
                    key={dir}
                    onClick={() => browse(`${current}/${dir}`)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-text-primary transition-colors hover:bg-bg-elevated"
                  >
                    <Folder size={13} className="flex-shrink-0 text-text-muted" />
                    <span className="flex-1 truncate">{dir}</span>
                    <ChevronRight size={12} className="flex-shrink-0 text-text-muted" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button onClick={onClose} className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary">
            取消
          </button>
          <button
            onClick={() => { onSelect(current); onClose(); }}
            disabled={!current}
            className="rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
          >
            选择此目录
          </button>
        </div>
      </div>
    </div>
  );
}
