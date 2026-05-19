import type { PhaseType } from '../../types/api';

const PHASE_QUICK_PROMPTS: Record<PhaseType, string[]> = {
  clarification: [
    '这是一个全新功能，从零开始',
    '这是对现有功能的优化改进',
    '先帮我梳理一下核心问题',
  ],
  ui_design: [
    '参考主流产品的设计模式',
    '优先移动端体验',
    '我有一些设计想法想讨论',
  ],
  architecture: [
    '用现有技术栈实现',
    '对性能要求比较高',
    '需要考虑后续扩展性',
  ],
  development: [
    '先从核心逻辑开始',
    '先写测试再实现',
    '有哪些可以复用的模块？',
  ],
  testing: [
    '重点测试核心流程',
    '帮我列出需要覆盖的场景',
    '有哪些边缘情况需要注意？',
  ],
  deployment: [
    '走标准部署流程',
    '需要灰度发布',
    '有什么需要提前准备的？',
  ],
  extraction: [
    '这次项目有不少值得记录的',
    '帮我总结关键决策点',
    '有哪些经验可以复用？',
  ],
};

export function QuickPrompts({ phase, onSelect }: { phase: PhaseType; onSelect: (text: string) => void }) {
  const prompts = PHASE_QUICK_PROMPTS[phase];
  return (
    <div className="flex flex-wrap gap-1.5 px-4 pt-2.5">
      {prompts.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="rounded-full border border-border bg-bg-card px-2.5 py-1 text-[10px] text-text-secondary transition-colors hover:border-accent/30 hover:text-accent"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
