import { Play, Sparkles, CheckCircle, ChevronRight, Loader2 } from 'lucide-react';
import type { PhaseStatus } from '../../types/api';

interface SmartActionBarProps {
  phaseStatus: PhaseStatus;
  phaseLabel: string;
  hasArtifact: boolean;
  hasMessages: boolean;
  canSkip: boolean;
  actionLoading: boolean;
  generating: boolean;
  onStartPhase: () => void;
  onGenerate: () => void;
  onConfirm: () => void;
  onSkip: () => void;
}

export function SmartActionBar({
  phaseStatus,
  phaseLabel,
  hasArtifact,
  hasMessages,
  canSkip,
  actionLoading,
  generating,
  onStartPhase,
  onGenerate,
  onConfirm,
  onSkip,
}: SmartActionBarProps) {
  let hint = '';
  let primaryLabel = '';
  let primaryAction: (() => void) | null = null;
  let primaryIcon: React.ReactNode = null;
  let showSkip = false;

  if (phaseStatus === 'pending') {
    hint = `准备好了？开始${phaseLabel}阶段`;
    primaryLabel = `开始${phaseLabel}`;
    primaryAction = onStartPhase;
    primaryIcon = <Play size={12} />;
    showSkip = canSkip;
  } else if (phaseStatus === 'active' && !hasArtifact && !hasMessages) {
    hint = `在右侧与 AI 对话，讨论${phaseLabel}方案`;
    primaryLabel = '';
    primaryAction = null;
  } else if (phaseStatus === 'active' && !hasArtifact && hasMessages) {
    hint = '对话信息已积累，可以生成结构化产出物';
    primaryLabel = '生成产出物';
    primaryAction = onGenerate;
    primaryIcon = generating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />;
    showSkip = canSkip;
  } else if (phaseStatus === 'active' && hasArtifact) {
    hint = '产出物已生成，审阅后确认进入下一阶段（需通过质量门禁）';
    primaryLabel = '确认并继续';
    primaryAction = onConfirm;
    primaryIcon = <CheckCircle size={12} />;
  } else if (phaseStatus === 'awaiting_confirm') {
    hint = '请审阅产出物，确认后自动推进';
    primaryLabel = '确认并继续';
    primaryAction = onConfirm;
    primaryIcon = <CheckCircle size={12} />;
  }

  return (
    <div className="flex items-center justify-between border-t border-border bg-bg-elevated/50 px-5 py-2.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/10">
          <Sparkles size={10} className="text-accent" />
        </span>
        <span className="text-[11px] text-text-secondary">{hint}</span>
      </div>
      <div className="flex items-center gap-2">
        {showSkip && (
          <button
            onClick={onSkip}
            disabled={actionLoading}
            className="text-[11px] text-text-muted transition-colors hover:text-text-secondary disabled:opacity-30"
          >
            跳过
          </button>
        )}
        {primaryAction && (
          <button
            onClick={primaryAction}
            disabled={actionLoading || generating}
            className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {primaryIcon}
            {primaryLabel}
            {(phaseStatus === 'active' && hasArtifact) || phaseStatus === 'awaiting_confirm' ? (
              <ChevronRight size={11} />
            ) : null}
          </button>
        )}
      </div>
    </div>
  );
}
