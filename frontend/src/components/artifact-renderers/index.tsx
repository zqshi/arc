import { lazy, Suspense } from 'react';
import { CodeBlock } from './shared';
import { asString } from './utils';
import type { ArtifactType, ArtifactContent } from '../../types/api';

// 首屏不渲染产出物, 所有 renderer 懒加载, 按需切分 chunk。
const RequirementSpec = lazy(() => import('./RequirementSpec'));
const InteractionDesign = lazy(() => import('./InteractionDesign'));
const UISpec = lazy(() => import('./UISpec'));
const Prototype = lazy(() => import('./Prototype'));
const UIDesign = lazy(() => import('./UIDesign'));
const TechArchitecture = lazy(() => import('./TechArchitecture'));
const DevReport = lazy(() => import('./DevReport'));
const TestReport = lazy(() => import('./TestReport'));
const DeployReport = lazy(() => import('./DeployReport'));
const ExperienceCard = lazy(() => import('./ExperienceCard'));
const AppCode = lazy(() => import('./AppCode'));
const ServiceSpec = lazy(() => import('./ServiceSpec'));
const Build = lazy(() => import('./Build'));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyContent = any;

interface Props {
  artifactType: ArtifactType;
  content: ArtifactContent;
}

const RENDERERS: Record<string, React.ComponentType<{ content: AnyContent }>> = {
  requirement_spec: RequirementSpec,
  interaction_design: InteractionDesign,
  ui_spec: UISpec,
  prototype: Prototype,
  tech_architecture: TechArchitecture,
  dev_report: DevReport,
  test_report: TestReport,
  deploy_report: DeployReport,
  experience_card: ExperienceCard,
  ui_design: UIDesign,
  app_code: AppCode,
  service_spec: ServiceSpec,
  build: Build,
};

function RendererFallback() {
  return <div className="h-32 animate-pulse rounded bg-bg-card" />;
}

export default function ArtifactRenderer({ artifactType, content }: Props) {
  const Renderer = RENDERERS[artifactType];

  if (!Renderer) {
    return (
      <div>
        <p className="mb-2 text-[11px] text-text-muted">未知产出物类型: {artifactType}</p>
        <CodeBlock>{asString(content)}</CodeBlock>
      </div>
    );
  }

  return (
    <Suspense fallback={<RendererFallback />}>
      <Renderer content={content} />
    </Suspense>
  );
}
