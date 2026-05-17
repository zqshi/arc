import { FileText, Users, Target, Shield, CheckSquare, AlertTriangle } from 'lucide-react';
import { SectionCard, TextBlock, asString } from './shared';

interface Props {
  content: Record<string, unknown>;
}

const SECTIONS = [
  { key: 'background', title: '需求背景', icon: <FileText size={13} /> },
  { key: 'user_scenarios', title: '用户场景', icon: <Users size={13} /> },
  { key: 'goals', title: '目标', icon: <Target size={13} /> },
  { key: 'boundaries', title: '边界条件', icon: <Shield size={13} /> },
  { key: 'acceptance_criteria', title: '验收标准', icon: <CheckSquare size={13} /> },
  { key: 'risk_assessment', title: '风险评估', icon: <AlertTriangle size={13} />, variant: 'warning' as const },
];

export default function RequirementSpec({ content }: Props) {
  return (
    <div>
      {SECTIONS.map(({ key, title, icon, variant }) => {
        const value = asString(content[key]);
        if (!value) return null;
        return (
          <SectionCard key={key} icon={icon} title={title} variant={variant}>
            <TextBlock>{value}</TextBlock>
          </SectionCard>
        );
      })}
    </div>
  );
}
