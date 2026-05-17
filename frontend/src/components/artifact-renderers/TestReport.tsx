import { CheckCircle, XCircle, HelpCircle, Bug, BarChart3 } from 'lucide-react';
import { SectionCard, TextBlock, StatusDot, Badge, asString, asArray } from './shared';

interface Props {
  content: Record<string, unknown>;
}

interface CriteriaItem {
  criteria?: string;
  status?: string;
  evidence?: string;
}

interface IssueItem {
  description?: string;
  severity?: string;
  suggestion?: string;
}

export default function TestReport({ content }: Props) {
  const criteria = asArray(content.criteria_verification) as CriteriaItem[];
  const issues = asArray(content.issues_found) as IssueItem[];
  const coverageSummary = asString(content.coverage_summary);

  const statusIcon = (s?: string) => {
    switch (s) {
      case 'pass':
        return <CheckCircle size={13} className="text-status-done" />;
      case 'fail':
        return <XCircle size={13} className="text-status-error" />;
      default:
        return <HelpCircle size={13} className="text-text-muted" />;
    }
  };

  const severityVariant = (s?: string): 'error' | 'warning' | 'default' => {
    switch (s) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      default: return 'default';
    }
  };

  return (
    <div>
      {criteria.length > 0 && (
        <SectionCard icon={<CheckCircle size={13} />} title="验收标准验证">
          <div className="space-y-1.5">
            {criteria.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-md border border-border/30 bg-bg-card px-3 py-2"
              >
                <span className="mt-0.5 flex-shrink-0">{statusIcon(item.status)}</span>
                <div className="flex-1">
                  <p className="text-xs font-medium text-text-primary">{item.criteria}</p>
                  {item.evidence && (
                    <p className="mt-0.5 text-[11px] text-text-secondary">{item.evidence}</p>
                  )}
                </div>
                <StatusDot status={item.status === 'pass' ? 'pass' : item.status === 'fail' ? 'fail' : 'unknown'} />
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {issues.length > 0 && (
        <SectionCard icon={<Bug size={13} />} title="发现的问题" variant="warning">
          <div className="space-y-2">
            {issues.map((issue, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant={severityVariant(issue.severity)}>
                    {issue.severity || 'unknown'}
                  </Badge>
                  <span className="text-xs font-medium text-text-primary">{issue.description}</span>
                </div>
                {issue.suggestion && (
                  <p className="text-[11px] text-text-secondary">建议: {issue.suggestion}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {coverageSummary && (
        <SectionCard icon={<BarChart3 size={13} />} title="覆盖率总结" variant="success">
          <TextBlock>{coverageSummary}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
