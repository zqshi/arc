import { Badge, LabeledField, SectionTitle } from './shared';

interface Content {
  build_status?: 'success' | 'failed' | 'building';
  build_target?: string;
  artifact_path?: string;
}

/**
 * v6.9: BUILD artifact 渲染器 — 原生客户端构建产物锚点 (BINARY_APP)。
 *
 * 仅 BINARY_APP 项目产出 (后端 _try_produce_build_artifact 类型守卫 +
 * DELIVERABLES_BY_TYPE 仅 BINARY_APP 含 build; 非 app 类 tracker.required 不含此交付物,
 * DeliverableSidebar 不显示)。展示构建状态/目标平台/产物路径, 供部署门禁/签名/分发读取。
 */
export default function Build({ content }: { content: Content }) {
  const status = content.build_status;
  const statusVariant =
    status === 'success' ? 'success' : status === 'failed' ? 'error' : 'warning';
  const statusLabel =
    status === 'success'
      ? '构建成功'
      : status === 'failed'
        ? '构建失败'
        : status === 'building'
          ? '构建中'
          : '未知状态';

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <SectionTitle>构建产物</SectionTitle>
        <Badge variant={statusVariant}>{statusLabel}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <LabeledField label="目标平台" value={content.build_target} mono />
        <LabeledField label="产物路径" value={content.artifact_path} mono />
      </div>
      <p className="text-[11px] text-text-muted">
        原生客户端构建锚点 — 供部署门禁/签名/分发读取 (BUILD artifact, v6.9)。
      </p>
    </div>
  );
}
