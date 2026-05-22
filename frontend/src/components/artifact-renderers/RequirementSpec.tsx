import { FileText, Users, Target, Shield, CheckSquare, AlertTriangle, Zap, HelpCircle } from 'lucide-react';
import { SectionCard, TextBlock, Badge } from './shared';
import { asString, asArray } from './utils';

interface Props {
  content: Record<string, unknown>;
}

interface TargetUser {
  type: string;
  traits: string;
  core_need: string;
}

interface UserStory {
  role: string;
  goal: string;
  benefit: string;
  priority: string;
  acceptance: string;
}

interface AcceptanceCriteria {
  id: string;
  scenario: string;
  steps: string;
  expected: string;
  priority: string;
}

interface RiskItem {
  risk: string;
  probability: string;
  impact: string;
  mitigation: string;
}

interface Assumption {
  assumption: string;
  confidence: string;
  validation_method: string;
}

function priorityVariant(p: string): 'error' | 'warning' | 'default' {
  if (p === 'P0') return 'error';
  if (p === 'P1') return 'warning';
  return 'default';
}

function levelVariant(level: string): 'error' | 'warning' | 'success' {
  if (level === '高') return 'error';
  if (level === '中') return 'warning';
  return 'success';
}

export default function RequirementSpec({ content }: Props) {
  const background = asString(content.background);
  const targetUsers = asArray(content.target_users) as TargetUser[];
  const coreValue = content.core_value as Record<string, string> | undefined;
  const userStories = asArray(content.user_stories) as UserStory[];
  const userScenarios = asString(content.user_scenarios);
  const boundaries = content.boundaries as { in_scope?: string[]; out_of_scope?: string[]; constraints?: string[] } | undefined;
  const criteria = asArray(content.acceptance_criteria) as AcceptanceCriteria[];
  const risks = asArray(content.risk_assessment) as RiskItem[];
  const assumptions = asArray(content.assumptions) as Assumption[];

  return (
    <div>
      {background && (
        <SectionCard icon={<FileText size={13} />} title="需求背景">
          <TextBlock>{background}</TextBlock>
        </SectionCard>
      )}

      {targetUsers.length > 0 && (
        <SectionCard icon={<Users size={13} />} title="目标用户">
          <div className="space-y-2.5">
            {targetUsers.map((u, i) => (
              <div key={i} className="rounded-md border border-border/50 px-3 py-2">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-semibold text-text-primary">{u.type}</span>
                </div>
                <p className="mb-1 text-xs text-text-muted">{u.traits}</p>
                <p className="text-xs text-text-secondary">
                  <span className="font-medium text-accent">核心诉求：</span>{u.core_need}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {coreValue && (
        <SectionCard icon={<Target size={13} />} title="核心价值">
          <div className="space-y-2">
            {coreValue.user_value && (
              <div className="text-xs text-text-secondary">
                <span className="font-medium text-text-primary">用户价值：</span>{coreValue.user_value}
              </div>
            )}
            {coreValue.business_value && (
              <div className="text-xs text-text-secondary">
                <span className="font-medium text-text-primary">商业价值：</span>{coreValue.business_value}
              </div>
            )}
            {coreValue.tech_value && (
              <div className="text-xs text-text-secondary">
                <span className="font-medium text-text-primary">技术价值：</span>{coreValue.tech_value}
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {userStories.length > 0 && (
        <SectionCard icon={<Zap size={13} />} title="用户故事">
          <div className="space-y-2.5">
            {userStories.map((s, i) => (
              <div key={i} className="rounded-md border border-border/50 px-3 py-2">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant={priorityVariant(s.priority)}>{s.priority}</Badge>
                  <span className="text-xs text-text-primary">作为 <b>{s.role}</b></span>
                </div>
                <p className="text-xs text-text-secondary">
                  <span className="font-medium">目标：</span>{s.goal}
                </p>
                <p className="text-xs text-text-secondary">
                  <span className="font-medium">收益：</span>{s.benefit}
                </p>
                {s.acceptance && (
                  <p className="mt-1 text-xs text-text-muted">
                    <span className="font-medium">验收：</span>{s.acceptance}
                  </p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {userScenarios && (
        <SectionCard icon={<Users size={13} />} title="用户场景">
          <TextBlock>{userScenarios}</TextBlock>
        </SectionCard>
      )}

      {boundaries && (
        <SectionCard icon={<Shield size={13} />} title="边界条件">
          <div className="space-y-2.5">
            {boundaries.in_scope && boundaries.in_scope.length > 0 && (
              <div>
                <h5 className="mb-1 text-[11px] font-semibold text-status-done">范围内</h5>
                <ul className="space-y-0.5">
                  {boundaries.in_scope.map((item, i) => (
                    <li key={i} className="flex gap-1.5 text-xs text-text-secondary">
                      <span className="text-status-done">+</span>{item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {boundaries.out_of_scope && boundaries.out_of_scope.length > 0 && (
              <div>
                <h5 className="mb-1 text-[11px] font-semibold text-status-error">范围外</h5>
                <ul className="space-y-0.5">
                  {boundaries.out_of_scope.map((item, i) => (
                    <li key={i} className="flex gap-1.5 text-xs text-text-secondary">
                      <span className="text-status-error">-</span>{item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {boundaries.constraints && boundaries.constraints.length > 0 && (
              <div>
                <h5 className="mb-1 text-[11px] font-semibold text-text-muted">约束条件</h5>
                <ul className="space-y-0.5">
                  {boundaries.constraints.map((item, i) => (
                    <li key={i} className="flex gap-1.5 text-xs text-text-secondary">
                      <span className="text-text-muted">!</span>{item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {criteria.length > 0 && (
        <SectionCard icon={<CheckSquare size={13} />} title="验收标准">
          <div className="space-y-2">
            {criteria.map((ac, i) => (
              <div key={i} className="rounded-md border border-border/50 px-3 py-2">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-[10px] font-mono font-medium text-accent">{ac.id}</span>
                  <Badge variant={priorityVariant(ac.priority)}>{ac.priority}</Badge>
                </div>
                <p className="text-xs text-text-secondary"><span className="font-medium">场景：</span>{ac.scenario}</p>
                <p className="text-xs text-text-secondary"><span className="font-medium">步骤：</span>{ac.steps}</p>
                <p className="text-xs text-text-secondary"><span className="font-medium">预期：</span>{ac.expected}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {risks.length > 0 && (
        <SectionCard icon={<AlertTriangle size={13} />} title="风险评估" variant="warning">
          <div className="space-y-2">
            {risks.map((r, i) => (
              <div key={i} className="rounded-md border border-border/50 px-3 py-2">
                <p className="mb-1 text-xs font-medium text-text-primary">{r.risk}</p>
                <div className="mb-1 flex gap-2">
                  <span className="text-[10px] text-text-muted">
                    概率 <Badge variant={levelVariant(r.probability)}>{r.probability}</Badge>
                  </span>
                  <span className="text-[10px] text-text-muted">
                    影响 <Badge variant={levelVariant(r.impact)}>{r.impact}</Badge>
                  </span>
                </div>
                <p className="text-xs text-text-secondary"><span className="font-medium">应对：</span>{r.mitigation}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {assumptions.length > 0 && (
        <SectionCard icon={<HelpCircle size={13} />} title="关键假设">
          <div className="space-y-2">
            {assumptions.map((a, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border border-border/50 px-3 py-2">
                <div className="flex-1">
                  <p className="text-xs text-text-secondary">{a.assumption}</p>
                  <p className="mt-0.5 text-[10px] text-text-muted">验证方式：{a.validation_method}</p>
                </div>
                <Badge variant={levelVariant(a.confidence)}>{a.confidence}</Badge>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
