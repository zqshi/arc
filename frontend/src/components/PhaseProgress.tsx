import type { PhaseType } from '../types/api';
import { PHASE_ORDER, PHASE_LABELS } from '../types/api';

export default function PhaseProgress({ currentPhase }: { currentPhase: PhaseType }) {
  const currentIdx = PHASE_ORDER.indexOf(currentPhase);

  return (
    <div className="flex flex-shrink-0 items-center gap-0.5" title={`当前: ${PHASE_LABELS[currentPhase]}`}>
      {PHASE_ORDER.map((pt, i) => (
        <div
          key={pt}
          className={`h-1 w-2.5 rounded-full transition-colors ${
            i < currentIdx
              ? 'bg-status-done'
              : i === currentIdx
              ? 'bg-accent'
              : 'bg-border'
          }`}
        />
      ))}
      <span className="ml-1.5 text-[9px] text-text-muted">{PHASE_LABELS[currentPhase]}</span>
    </div>
  );
}
