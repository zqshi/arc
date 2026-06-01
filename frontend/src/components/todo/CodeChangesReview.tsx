import { useState } from 'react';
import { GitBranch, Check, X, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { useToast } from '../Toast';

export interface CodeChangesInfo {
  todoId: string;
  filesChanged: number;
  insertions: number;
  deletions: number;
  diffStat: string;
  diffPreview: string;
}

interface Props {
  changes: CodeChangesInfo;
  onDismiss: () => void;
  onPushComplete: (result: { commit_sha: string; branch: string }) => void;
}

export function CodeChangesReview({ changes, onDismiss, onPushComplete }: Props) {
  const { toast } = useToast();
  const [pushing, setPushing] = useState(false);
  const [message, setMessage] = useState(`feat: ${changes.todoId.slice(0, 8)} 功能实现`);
  const [showDiff, setShowDiff] = useState(false);
  const [showMessageInput, setShowMessageInput] = useState(false);

  const handlePush = async () => {
    setPushing(true);
    try {
      const result = await api.confirmPush(changes.todoId, message);
      if (result.success) {
        toast(`已推送到 ${result.branch} (${result.commit_sha.slice(0, 7)})`, 'success');
        onPushComplete({ commit_sha: result.commit_sha, branch: result.branch });
      } else {
        toast('推送失败，请检查 Git 配置', 'error');
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : '推送失败', 'error');
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="rounded-lg border border-accent/30 bg-accent/5 p-3 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch size={14} className="text-accent" />
          <span className="text-xs font-medium text-text-primary">
            检测到代码变更
          </span>
          <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-medium text-accent">
            {changes.filesChanged} 文件 · +{changes.insertions} -{changes.deletions}
          </span>
        </div>
        <button
          onClick={onDismiss}
          className="flex h-5 w-5 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-secondary"
          title="暂不推送"
        >
          <X size={12} />
        </button>
      </div>

      {/* Diff stat */}
      {changes.diffStat && (
        <div className="rounded-md bg-bg-elevated px-2.5 py-1.5">
          <pre className="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-text-secondary">
            {changes.diffStat}
          </pre>
        </div>
      )}

      {/* Diff preview toggle */}
      {changes.diffPreview && (
        <button
          onClick={() => setShowDiff(!showDiff)}
          className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary"
        >
          {showDiff ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          {showDiff ? '收起 diff' : '查看 diff 详情'}
        </button>
      )}
      {showDiff && (
        <div className="max-h-48 overflow-y-auto rounded-md border border-border bg-[#1a1b26] p-2.5">
          <pre className="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-[#9ece6a]">
            {changes.diffPreview}
          </pre>
        </div>
      )}

      {/* Commit message input */}
      <button
        onClick={() => setShowMessageInput(!showMessageInput)}
        className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary"
      >
        {showMessageInput ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        自定义 commit message
      </button>
      {showMessageInput && (
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="h-7 w-full rounded-md border border-border bg-bg-input px-2.5 font-mono text-[11px] text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          placeholder="feat: ..."
        />
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handlePush}
          disabled={pushing || !message.trim()}
          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-[11px] font-medium text-white transition-opacity hover:bg-accent-hover disabled:opacity-50"
        >
          {pushing ? (
            <><Loader2 size={11} className="animate-spin" /> 推送中...</>
          ) : (
            <><Check size={11} /> 确认推送</>
          )}
        </button>
        <button
          onClick={onDismiss}
          className="rounded-md border border-border px-3 py-1.5 text-[11px] text-text-secondary transition-colors hover:bg-bg-elevated"
        >
          暂不推送
        </button>
        <p className="ml-auto text-[9px] text-text-muted">
          变更保留在本地，可稍后手动推送
        </p>
      </div>
    </div>
  );
}
