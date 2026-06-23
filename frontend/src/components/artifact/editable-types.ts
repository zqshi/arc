/**
 * v5.5.0: 前端 artifact 可编辑类型镜像。
 *
 * 与后端 domain/artifact/policy.py 的 EDITABLE_FIELDS 保持一致。
 * - 文档类 artifact: 整体 JSON 可编辑 (后端 __all__ 白名单)
 * - 工程产物 (APP_CODE/PROTOTYPE): 只读, 不显示编辑按钮
 * - SERVICE_SPEC: 仅 notes 字段可编辑 (v5.5.0 暂未暴露 UI, 留 v5.6.0)
 *
 * 改后端策略时同步更新此处。
 */
export const EDITABLE_ARTIFACT_TYPES = new Set<string>([
  'requirement_spec',
  'interaction_design',
  'ui_spec',
  'tech_architecture',
  'dev_report',
  'test_report',
  'deploy_report',
  'experience_card',
]);

export function isArtifactEditable(type: string): boolean {
  return EDITABLE_ARTIFACT_TYPES.has(type);
}
