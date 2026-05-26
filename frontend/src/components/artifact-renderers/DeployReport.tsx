import { Terminal, Globe, HeartPulse, RotateCcw } from 'lucide-react';
import { SectionCard, TerminalBlock, TextBlock, Badge } from './shared';
import { asString } from './utils';
interface Props {
  content: Record<string, unknown>;
}

export default function DeployReport({ content }: Props) {
  const deployLog = asString(content.deploy_log);
  const serviceUrl = asString(content.service_url);
  const healthCheck = asString(content.health_check_result);
  const rollbackPlan = asString(content.rollback_plan);

  const healthStatus = healthCheck.toLowerCase().includes('pass') ||
    healthCheck.toLowerCase().includes('healthy') ||
    healthCheck.toLowerCase().includes('ok')
    ? 'success' as const
    : 'warning' as const;

  return (
    <div>
      {serviceUrl && (
        <SectionCard icon={<Globe size={13} />} title="服务地址">
          <a
            href={serviceUrl.startsWith('http') ? serviceUrl : `https://${serviceUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-accent underline decoration-accent/30 hover:decoration-accent"
          >
            {serviceUrl}
          </a>
        </SectionCard>
      )}

      {healthCheck && (
        <SectionCard icon={<HeartPulse size={13} />} title="健康检查" variant={healthStatus}>
          <div className="flex items-center gap-2">
            <Badge variant={healthStatus}>{healthStatus === 'success' ? '通过' : '异常'}</Badge>
            <span className="text-xs text-text-secondary">{healthCheck}</span>
          </div>
        </SectionCard>
      )}

      {deployLog && (
        <SectionCard icon={<Terminal size={13} />} title="部署日志">
          <TerminalBlock>{deployLog}</TerminalBlock>
        </SectionCard>
      )}

      {rollbackPlan && (
        <SectionCard icon={<RotateCcw size={13} />} title="回滚方案">
          <TextBlock>{rollbackPlan}</TextBlock>
        </SectionCard>
      )}
    </div>
  );
}
