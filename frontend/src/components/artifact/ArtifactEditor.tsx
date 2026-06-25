import { useState } from 'react';
import { Check, X, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';
import type { Artifact } from '../../types/api';

interface Props {
  artifact: Artifact;
  todoId: string;
  onSave: (updated: Artifact) => void;
  onCancel: () => void;
}

/**
 * v5.5.0: Artifact JSON 编辑器。
 *
 * 用户场景：在 DeliverableDrawer 中点击"编辑"切到此组件。
 * 保存调用 PATCH /api/todos/{todoId}/artifacts/{artifactId}，
 * 后端按 EDITABLE_FIELDS 白名单校验，不可编辑字段返回 400 + 字段名。
 */
export default function ArtifactEditor({ artifact, todoId, onSave, onCancel }: Props) {
  const [raw, setRaw] = useState(() => JSON.stringify(artifact.content ?? {}, null, 2));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch {
      setError('JSON 格式错误，请检查');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateArtifact(todoId, artifact.id, parsed);
      onSave(updated);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败';
      // 后端 ValueError 返回的 detail 格式: "不可编辑字段: a, b (artifact_type=...)"
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-2 text-[11px] text-text-muted">
        编辑模式 · 仅可编辑字段会保存成功 (后端白名单校验)
      </div>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        spellCheck={false}
        className="flex-1 resize-none bg-bg-elevated p-4 font-mono text-xs text-text-primary outline-none"
        aria-label="artifact-content-editor"
      />
      {error && (
        <div
          role="alert"
          className="mx-4 mb-2 flex items-start gap-2 rounded-md border border-status-error/30 bg-status-error/5 px-3 py-2 text-[11px] text-status-error"
        >
          <AlertCircle size={13} className="mt-0.5 flex-shrink-0" />
          <span className="break-all">{error}</span>
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-border px-4 py-2.5">
        <button
          onClick={onCancel}
          disabled={saving}
          className="flex items-center gap-1 rounded-md px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-50"
        >
          <X size={13} /> 取消
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
        >
          <Check size={13} /> {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
}
