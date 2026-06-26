import { useState, useEffect, useCallback } from 'react';
import { Loader2, CheckSquare } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { useToast } from '../Toast';
import { PIPELINE_PHASES } from '../../types/api';
import type { Capability, CapabilityType, PhaseCapabilities } from '../../types/api';

interface PhaseCapabilitiesSectionProps {
  projectId: string;
  phaseCapabilities: PhaseCapabilities;
  onRefresh: () => void;
}

const TYPE_LABEL: Record<CapabilityType, string> = { agent: 'Agent', skill: 'Skill', mcp: 'MCP' };
const TYPE_ORDER: CapabilityType[] = ['agent', 'skill', 'mcp'];

function groupByType(caps: Capability[]): Record<string, Capability[]> {
  return caps.reduce((acc, c) => {
    (acc[c.type] ??= []).push(c);
    return acc;
  }, {} as Record<string, Capability[]>);
}

/**
 * 环节能力配置 (v6.8.0 W3.4) — 7 阶段 × 能力勾选，即时保存。
 * 对接 PUT /api/projects/{id}/pipeline/phase-capabilities (单 phase 增量, admin only)。
 */
export function PhaseCapabilitiesSection({ projectId, phaseCapabilities, onRefresh }: PhaseCapabilitiesSectionProps) {
  const { toast } = useToast();
  const [caps, setCaps] = useState<Capability[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PhaseCapabilities>({});
  const [savingPhase, setSavingPhase] = useState<string | null>(null);

  useEffect(() => { setSelected(phaseCapabilities || {}); }, [phaseCapabilities]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCaps(await api.listCapabilities({ status: 'active' }));
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : '加载能力失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (phase: string, capId: string) => {
    const current = selected[phase] ?? [];
    const isOn = current.includes(capId);
    const nextIds = isOn ? current.filter((id) => id !== capId) : [...current, capId];
    const snapshot = selected;
    setSelected((p) => ({ ...p, [phase]: nextIds }));
    setSavingPhase(phase);
    try {
      await api.updatePhaseCapabilities(projectId, phase, nextIds);
      toast('环节能力已更新', 'success');
      onRefresh();
    } catch (err) {
      setSelected(snapshot);
      toast(err instanceof ApiError ? err.detail : '保存失败', 'error');
    } finally {
      setSavingPhase(null);
    }
  };

  const grouped = groupByType(caps);

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4 lg:col-span-2">
      <div className="mb-1 flex items-center gap-2">
        <CheckSquare size={13} className="text-text-muted" />
        <p className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">环节能力配置</p>
      </div>
      <p className="mb-3 text-[11px] text-text-muted">为每个研发阶段勾选启用能力。执行时该阶段对话注入对应能力，门禁按启用能力生成检查项。改动即时保存。</p>

      {loading ? (
        <div className="flex items-center justify-center py-6 text-text-muted">
          <Loader2 size={14} className="animate-spin" />
        </div>
      ) : caps.length === 0 ? (
        <p className="py-4 text-center text-[11px] text-text-muted">暂无可用能力。请先在「系统设置 → 能力管理」创建并启用。</p>
      ) : (
        <div className="space-y-3">
          {PIPELINE_PHASES.map(({ key, label }) => {
            const phaseCaps = selected[key] ?? [];
            const saving = savingPhase === key;
            return (
              <div key={key} className="rounded-md border border-border/60 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-text-primary">{label}</span>
                  <span className="flex items-center gap-1.5 text-[10px] text-text-muted">
                    {saving && <Loader2 size={10} className="animate-spin" />}
                    已选 {phaseCaps.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {TYPE_ORDER.map((t) => {
                    const group = grouped[t];
                    if (!group || group.length === 0) return null;
                    return (
                      <div key={t}>
                        <p className="mb-1 text-[10px] font-medium text-text-tertiary">{TYPE_LABEL[t]}</p>
                        <div className="flex flex-wrap gap-2">
                          {group.map((c) => {
                            const on = phaseCaps.includes(c.id);
                            return (
                              <button
                                key={c.id}
                                type="button"
                                onClick={() => toggle(key, c.id)}
                                className={`rounded-md border px-2.5 py-1 text-[11px] transition-all ${on ? 'border-accent/50 bg-accent/10 text-accent' : 'border-border text-text-secondary hover:border-border-active'}`}
                              >
                                {c.name}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
