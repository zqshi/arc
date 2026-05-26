import { Target, Lightbulb, AlertTriangle, BookOpen, Tag } from 'lucide-react';
import { SectionCard, TextBlock } from './shared';
import { asString, asArray } from './utils';
interface Props {
  content: Record<string, unknown>;
}

interface Decision {
  point?: string;
  chosen?: string;
  reason?: string;
}

interface Pitfall {
  issue?: string;
  cause?: string;
  fix?: string;
}

export default function ExperienceCard({ content }: Props) {
  const problem = asString(content.problem);
  const solution = asString(content.solution);
  const decisions = asArray(content.decisions) as Decision[];
  const pitfalls = asArray(content.pitfalls) as Pitfall[];
  const scenarios = asString(content.applicable_scenarios);
  const tags = asArray(content.tags) as string[];

  return (
    <div>
      {problem && (
        <SectionCard icon={<Target size={13} />} title="问题">
          <TextBlock>{problem}</TextBlock>
        </SectionCard>
      )}

      {solution && (
        <SectionCard icon={<Lightbulb size={13} />} title="解决方案">
          <TextBlock>{solution}</TextBlock>
        </SectionCard>
      )}

      {decisions.length > 0 && (
        <SectionCard icon={<BookOpen size={13} />} title="关键决策">
          <div className="space-y-2">
            {decisions.map((d, i) => (
              <div key={i} className="rounded-md border border-border/50 bg-bg-card p-2.5">
                <p className="text-xs font-medium text-text-primary">{d.point}</p>
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded bg-status-done/15 px-1.5 py-0.5 text-[10px] font-medium text-status-done">
                    {d.chosen}
                  </span>
                  {d.reason && (
                    <span className="text-[10px] text-text-secondary">{d.reason}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {pitfalls.length > 0 && (
        <SectionCard icon={<AlertTriangle size={13} />} title="踩坑记录" variant="warning">
          <div className="space-y-2">
            {pitfalls.map((p, i) => (
              <div key={i} className="rounded-md border border-status-error/15 bg-bg-card p-2.5">
                <p className="text-xs font-medium text-status-error/90">{p.issue}</p>
                {p.cause && (
                  <p className="mt-0.5 text-[11px] text-text-secondary">原因: {p.cause}</p>
                )}
                {p.fix && (
                  <p className="mt-0.5 text-[11px] text-text-secondary">解决: {p.fix}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {scenarios && (
        <SectionCard icon={<Target size={13} />} title="适用场景">
          <TextBlock>{scenarios}</TextBlock>
        </SectionCard>
      )}

      {tags.length > 0 && (
        <SectionCard icon={<Tag size={13} />} title="标签">
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag, i) => (
              <span key={i} className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                {typeof tag === 'string' ? tag : JSON.stringify(tag)}
              </span>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
