import { Terminal, GitCommit, TestTube, Lightbulb } from 'lucide-react';
import { SectionCard, TerminalBlock, TextBlock, NumberedList, asString, asArray } from './shared';

interface Props {
  content: Record<string, unknown>;
}

interface DecisionMade {
  decision?: string;
  reason?: string;
}

export default function DevReport({ content }: Props) {
  const executionLog = asString(content.execution_log);
  const codeChanges = asArray(content.code_changes) as string[];
  const testResults = asString(content.test_results);
  const decisionsMade = asArray(content.decisions_made) as DecisionMade[];

  return (
    <div>
      {executionLog && (
        <SectionCard icon={<Terminal size={13} />} title="执行日志">
          <TerminalBlock>{executionLog}</TerminalBlock>
        </SectionCard>
      )}

      {codeChanges.length > 0 && (
        <SectionCard icon={<GitCommit size={13} />} title="代码变更">
          <NumberedList items={codeChanges} />
        </SectionCard>
      )}

      {testResults && (
        <SectionCard icon={<TestTube size={13} />} title="测试结果" variant="success">
          <TextBlock>{testResults}</TextBlock>
        </SectionCard>
      )}

      {decisionsMade.length > 0 && (
        <SectionCard icon={<Lightbulb size={13} />} title="决策记录">
          <div className="space-y-2">
            {decisionsMade.map((d, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <p className="text-xs font-medium text-text-primary">{d.decision}</p>
                {d.reason && (
                  <p className="mt-0.5 text-[11px] text-text-secondary">原因: {d.reason}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
