import { CodeBlock } from './shared';
import { asString } from './utils';
import RequirementSpec from './RequirementSpec';
import InteractionDesign from './InteractionDesign';
import UISpec from './UISpec';
import Prototype from './Prototype';
import UIDesign from './UIDesign';
import TechArchitecture from './TechArchitecture';
import DevReport from './DevReport';
import TestReport from './TestReport';
import DeployReport from './DeployReport';
import ExperienceCard from './ExperienceCard';
import type { ArtifactType, ArtifactContent } from '../../types/api';
import type { SelectedElementInfo } from '../prototype/inspector';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyContent = any;

interface Props {
  artifactType: ArtifactType;
  content: ArtifactContent;
  onPrototypeModify?: (info: SelectedElementInfo, instruction: string) => void;
}

const RENDERERS: Record<string, React.ComponentType<{ content: AnyContent }>> = {
  requirement_spec: RequirementSpec,
  interaction_design: InteractionDesign,
  ui_spec: UISpec,
  tech_architecture: TechArchitecture,
  dev_report: DevReport,
  test_report: TestReport,
  deploy_report: DeployReport,
  experience_card: ExperienceCard,
  ui_design: UIDesign,
};

export default function ArtifactRenderer({ artifactType, content, onPrototypeModify }: Props) {
  // Prototype has special interactive props
  if (artifactType === 'prototype') {
    return <Prototype content={content as AnyContent} onRequestModify={onPrototypeModify} />;
  }

  const Renderer = RENDERERS[artifactType];

  if (!Renderer) {
    return (
      <div>
        <p className="mb-2 text-[11px] text-text-muted">未知产出物类型: {artifactType}</p>
        <CodeBlock>{asString(content)}</CodeBlock>
      </div>
    );
  }

  return <Renderer content={content} />;
}
