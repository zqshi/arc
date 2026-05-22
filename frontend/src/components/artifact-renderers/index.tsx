import { CodeBlock } from './shared';
import { asString } from './utils';
import RequirementSpec from './RequirementSpec';
import UIDesign from './UIDesign';
import TechArchitecture from './TechArchitecture';
import DevReport from './DevReport';
import TestReport from './TestReport';
import DeployReport from './DeployReport';
import ExperienceCard from './ExperienceCard';

interface Props {
  artifactType: string;
  content: Record<string, unknown>;
}

const RENDERERS: Record<string, React.ComponentType<{ content: Record<string, unknown> }>> = {
  requirement_spec: RequirementSpec,
  ui_design: UIDesign,
  tech_architecture: TechArchitecture,
  dev_report: DevReport,
  test_report: TestReport,
  deploy_report: DeployReport,
  experience_card: ExperienceCard,
};

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

  return <Renderer content={content} />;
}
