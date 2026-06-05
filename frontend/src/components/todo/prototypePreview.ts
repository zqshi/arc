/**
 * 原型预览工具 — 工程模式下直接打开部署 URL。
 */

export function openPrototypeInNewTab(content: Record<string, unknown>) {
  const previewUrl = content.preview_url as string | undefined;

  if (previewUrl) {
    window.open(previewUrl, '_blank');
    return;
  }

  // 无 URL 时提示
  const buildStatus = content.build_status as string | undefined;
  if (buildStatus === 'building') {
    alert('原型正在构建中，请稍后再试。');
  } else if (buildStatus === 'failed') {
    alert('原型构建失败，请查看 AI 对话中的错误信息。');
  } else {
    alert('暂无可预览的原型。请先完成设计阶段。');
  }
}
