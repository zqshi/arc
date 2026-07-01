import type { ReactNode } from 'react';
import { ChevronDown, Monitor, Sparkles, Loader2 } from 'lucide-react';
import MarkdownContent from '../components/MarkdownContent';
import { SuggestionsPanel } from '../components/project/SuggestionsPanel';
import type { Version } from '../types/api';

/** 版本选择器 (原型预览的版本切换) */
export function VersionPicker({
  previewableVersions,
  selectedVersion,
  protoVersionId,
  show,
  onToggle,
  onSelect,
}: {
  previewableVersions: Version[];
  selectedVersion?: Version;
  protoVersionId: string | null;
  show: boolean;
  onToggle: () => void;
  onSelect: (id: string | null) => void;
}): ReactNode {
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className="flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-[10px] text-text-muted hover:border-accent/50 hover:text-text-secondary transition-colors"
      >
        {selectedVersion?.name || '当前版本'}
        <ChevronDown size={10} />
      </button>
      {show && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[120px] rounded-md border border-border bg-bg-primary py-1 shadow-lg">
          <button
            onClick={() => onSelect(null)}
            className={`block w-full px-3 py-1.5 text-left text-[10px] hover:bg-bg-elevated ${!protoVersionId ? 'text-accent' : 'text-text-secondary'}`}
          >
            自动（当前版本）
          </button>
          {previewableVersions.map(v => (
            <button
              key={v.id}
              onClick={() => onSelect(v.id)}
              className={`block w-full px-3 py-1.5 text-left text-[10px] hover:bg-bg-elevated ${protoVersionId === v.id ? 'text-accent' : 'text-text-secondary'}`}
            >
              {v.name} {v.status === 'released' ? '✓' : ''}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** 原型预览按钮 */
export function PreviewButton({
  hasPrototype,
  totalPages,
  onClick,
}: {
  hasPrototype: boolean;
  totalPages: number;
  onClick: () => void;
}): ReactNode {
  return (
    <button
      onClick={onClick}
      disabled={!hasPrototype}
      className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors ${
        hasPrototype
          ? 'border-border text-text-muted hover:border-accent hover:text-accent'
          : 'border-border/50 text-text-muted/40 cursor-not-allowed'
      }`}
      title={hasPrototype
        ? `预览原型 (${totalPages} 个页面)`
        : '暂无原型页面，请先完成需求设计'
      }
    >
      <Monitor size={13} /> 预览原型
      {hasPrototype && totalPages > 0 && (
        <span className="ml-0.5 rounded bg-accent/10 px-1 py-0.5 text-[9px] text-accent">
          {totalPages}
        </span>
      )}
    </button>
  );
}

/** AI 迭代分析弹窗 */
export function AnalysisModal({
  analyzing,
  analysisResult,
  analysisCached,
  analysisSuggestions,
  existingTodoTitles,
  onClose,
  onCreateTodos,
}: {
  analyzing: boolean;
  analysisResult: string | null;
  analysisCached: boolean;
  analysisSuggestions: Array<{ priority: string; action: string; reason: string }>;
  existingTodoTitles: Set<string>;
  onClose: () => void;
  onCreateTodos: (items: Array<{ priority: string; action: string; reason: string }>) => Promise<void>;
}): ReactNode {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-3xl animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Sparkles size={14} className="text-accent" /> AI 迭代分析
            {analysisCached && (
              <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] font-normal text-text-muted">缓存</span>
            )}
          </h2>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-secondary transition-colors"
          >
            ×
          </button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-5 py-4">
          {analyzing ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={20} className="animate-spin text-accent" />
              <span className="ml-2 text-sm text-text-muted">AI 正在分析迭代状态...</span>
            </div>
          ) : analysisResult ? (
            <>
              <MarkdownContent content={analysisResult} />
              {analysisSuggestions.length > 0 && (
                <SuggestionsPanel
                  suggestions={analysisSuggestions}
                  existingTodoTitles={existingTodoTitles}
                  onCreateTodos={onCreateTodos}
                />
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
