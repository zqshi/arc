import { Terminal, GitCommit, TestTube, Lightbulb, CheckCircle2, XCircle, Clock, Layers } from 'lucide-react';
import { SectionCard, TerminalBlock, TextBlock, NumberedList, Badge, StatusDot } from './shared';
import { asString, asArray } from './utils';

interface Props {
  content: Record<string, unknown>;
}

interface DecisionMade {
  decision?: string;
  reason?: string;
  ddd_rationale?: string;
}

interface TestCase {
  name?: string;
  type?: string;
  target_aggregate?: string;
  given?: string;
  when?: string;
  then?: string;
  status?: 'pass' | 'fail' | 'pending';
}

interface CodeChange {
  file?: string;
  change_type?: string;
  description?: string;
  aggregate?: string;
}

function isNewFormat(content: Record<string, unknown>): boolean {
  return 'test_design' in content || 'implementation' in content || 'validation' in content;
}

function TestStatusIcon({ status }: { status?: string }) {
  if (status === 'pass') return <CheckCircle2 size={12} className="text-status-done" />;
  if (status === 'fail') return <XCircle size={12} className="text-status-error" />;
  return <Clock size={12} className="text-text-muted" />;
}

function NewFormatRenderer({ content }: Props) {
  const methodology = asString(content.methodology);
  const testDesign = content.test_design as { derived_from?: string[]; test_cases?: TestCase[] } | undefined;
  const implementation = content.implementation as { aggregates_touched?: string[]; code_changes?: CodeChange[]; invariants_enforced?: string[] } | undefined;
  const validation = content.validation as { all_tests_pass?: boolean; coverage_notes?: string; refactoring_done?: string[] } | undefined;
  const decisionsMade = asArray(content.decisions_made) as DecisionMade[];

  return (
    <div>
      {methodology && (
        <div className="mb-3 flex items-center gap-2">
          <Badge variant={methodology === 'ddd_tdd' ? 'success' : 'default'}>
            {methodology === 'ddd_tdd' ? 'DDD + TDD' : methodology}
          </Badge>
        </div>
      )}

      {testDesign && (testDesign.test_cases?.length ?? 0) > 0 && (
        <SectionCard icon={<TestTube size={13} />} title="测试设计">
          {testDesign.derived_from && testDesign.derived_from.length > 0 && (
            <p className="mb-2 text-[11px] text-text-muted">
              派生自: {testDesign.derived_from.join(', ')}
            </p>
          )}
          <div className="space-y-2">
            {testDesign.test_cases!.map((tc, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <div className="flex items-center gap-2">
                  <TestStatusIcon status={tc.status} />
                  <span className="text-xs font-medium text-text-primary">{tc.name}</span>
                  {tc.type && <Badge>{tc.type}</Badge>}
                  {tc.target_aggregate && (
                    <Badge variant="default">{tc.target_aggregate}</Badge>
                  )}
                </div>
                <div className="mt-1.5 space-y-0.5 pl-5 text-[11px] text-text-secondary">
                  {tc.given && <p><span className="font-medium text-text-tertiary">Given:</span> {tc.given}</p>}
                  {tc.when && <p><span className="font-medium text-text-tertiary">When:</span> {tc.when}</p>}
                  {tc.then && <p><span className="font-medium text-text-tertiary">Then:</span> {tc.then}</p>}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {implementation && (
        <SectionCard icon={<Layers size={13} />} title="实现">
          {implementation.aggregates_touched && implementation.aggregates_touched.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {implementation.aggregates_touched.map((agg, i) => (
                <Badge key={i}>{agg}</Badge>
              ))}
            </div>
          )}
          {implementation.code_changes && implementation.code_changes.length > 0 && (
            <div className="mb-2 space-y-1.5">
              {implementation.code_changes.map((cc, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                  <span className={`mt-0.5 inline-block rounded px-1 py-0.5 text-[10px] font-mono ${
                    cc.change_type === 'add' ? 'bg-status-done/15 text-status-done' :
                    cc.change_type === 'delete' ? 'bg-status-error/15 text-status-error' :
                    'bg-accent/10 text-accent'
                  }`}>
                    {cc.change_type}
                  </span>
                  <span className="font-mono text-[11px]">{cc.file}</span>
                  {cc.description && <span className="text-text-muted">— {cc.description}</span>}
                </div>
              ))}
            </div>
          )}
          {implementation.invariants_enforced && implementation.invariants_enforced.length > 0 && (
            <div className="mt-2 border-t border-border/30 pt-2">
              <p className="mb-1 text-[10px] font-semibold uppercase text-text-tertiary">不变量保护</p>
              <ul className="space-y-0.5">
                {implementation.invariants_enforced.map((inv, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-text-secondary">
                    <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full bg-accent" />
                    {inv}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>
      )}

      {validation && (
        <SectionCard
          icon={<CheckCircle2 size={13} />}
          title="验证"
          variant={validation.all_tests_pass ? 'success' : 'warning'}
        >
          <div className="flex items-center gap-2 mb-2">
            <StatusDot status={validation.all_tests_pass ? 'pass' : 'fail'} />
            <span className="text-xs text-text-secondary">
              {validation.all_tests_pass ? '全部测试通过' : '存在未通过测试'}
            </span>
          </div>
          {validation.coverage_notes && (
            <p className="text-[11px] text-text-muted mb-2">{validation.coverage_notes}</p>
          )}
          {validation.refactoring_done && validation.refactoring_done.length > 0 && (
            <div className="border-t border-border/30 pt-2">
              <p className="mb-1 text-[10px] font-semibold uppercase text-text-tertiary">重构项</p>
              <NumberedList items={validation.refactoring_done} />
            </div>
          )}
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
                {d.ddd_rationale && (
                  <p className="mt-0.5 text-[11px] text-text-muted italic">DDD: {d.ddd_rationale}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

function LegacyFormatRenderer({ content }: Props) {
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

export default function DevReport({ content }: Props) {
  if (isNewFormat(content)) {
    return <NewFormatRenderer content={content} />;
  }
  return <LegacyFormatRenderer content={content} />;
}
