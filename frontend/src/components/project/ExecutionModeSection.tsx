/**
 * ExecutionModeSection — 执行模式切换 + 自驾模式开关。
 */
import { Workflow, MessageSquare, AlertTriangle, Zap } from 'lucide-react';
import type { ExecutionMode } from '../../types/api';
import { EXECUTION_MODE_LABELS, EXECUTION_MODE_DESCRIPTIONS } from '../../types/api';

interface ExecutionModeSectionProps {
  executionMode: ExecutionMode;
  pipelineConfig: Record<string, unknown>;
  conversationConfig: Record<string, unknown>;
  impact: { active_count: number; pending_count: number } | null;
  impactLoaded: boolean;
  onChange: (mode: ExecutionMode, pipelineConfig: Record<string, unknown>, conversationConfig: Record<string, unknown>) => void;
}

export function ExecutionModeSection({
  executionMode, pipelineConfig, conversationConfig, impact, impactLoaded, onChange,
}: ExecutionModeSectionProps) {
  const isAutopilot = Boolean(pipelineConfig?.auto_advance) || conversationConfig?.agent_autonomy === 'full';

  const toggleAutopilot = () => {
    onChange(executionMode, {
      ...pipelineConfig,
      auto_advance: !isAutopilot,
    }, {
      ...conversationConfig,
      agent_autonomy: isAutopilot ? 'supervised' : 'full',
    });
  };

  return (
    <>
      {/* Execution Mode */}
      <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
        <p className="mb-3 text-[11px] font-medium text-text-tertiary uppercase tracking-wide">执行模式</p>
        <p className="mb-3 text-[11px] text-text-muted">决定项目中需求的推进方式。新创建的需求将继承此设置。</p>

        {/* Impact warning */}
        {impactLoaded && impact && impact.active_count > 0 && (
          <div className="mb-3 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
            <AlertTriangle size={13} className="mt-0.5 flex-shrink-0 text-amber-500" />
            <div className="text-[11px] text-amber-600">
              <span className="font-medium">当前有 {impact.active_count} 个进行中的需求</span>
              {impact.pending_count > 0 && <span>，{impact.pending_count} 个待启动的需求</span>}
              <span>。切换模式仅影响新建需求，已有需求保持原有模式不变。</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(['pipeline', 'conversation'] as ExecutionMode[]).map((mode) => {
            const isActive = executionMode === mode;
            const Icon = mode === 'pipeline' ? Workflow : MessageSquare;
            return (
              <button
                key={mode}
                onClick={() => onChange(mode, pipelineConfig, conversationConfig)}
                className={`flex flex-col items-start rounded-lg border p-3 text-left transition-all ${
                  isActive
                    ? 'border-accent/50 bg-accent/5 ring-1 ring-accent/20'
                    : 'border-border hover:border-border-active hover:bg-bg-elevated'
                }`}
              >
                <div className="mb-2 flex items-center gap-2">
                  <Icon size={14} className={isActive ? 'text-accent' : 'text-text-muted'} />
                  <span className={`text-xs font-medium ${isActive ? 'text-accent' : 'text-text-secondary'}`}>
                    {EXECUTION_MODE_LABELS[mode]}
                  </span>
                </div>
                <p className="text-[10px] leading-relaxed text-text-muted">
                  {EXECUTION_MODE_DESCRIPTIONS[mode]}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Autopilot */}
      <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
              isAutopilot ? 'bg-accent text-white' : 'bg-bg-elevated text-text-muted'
            }`}>
              <Zap size={16} />
            </div>
            <div>
              <p className="text-xs font-medium text-text-primary">自驾模式</p>
              <p className="text-[11px] text-text-muted">
                {executionMode === 'pipeline'
                  ? 'AI 自动通过阶段关卡，仅在异常时中断'
                  : 'Agent 完全自主推进，仅在异常时中断'}
              </p>
            </div>
          </div>
          <button
            onClick={toggleAutopilot}
            className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
              isAutopilot ? 'bg-accent' : 'bg-border'
            }`}
          >
            <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
              isAutopilot ? 'translate-x-5' : ''
            }`} />
          </button>
        </div>
      </div>
    </>
  );
}
