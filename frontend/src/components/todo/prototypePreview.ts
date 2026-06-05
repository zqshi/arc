/**
 * 原型预览工具 — 工程模式下直接打开部署 URL 或本地 serve。
 */

import { API_BASE } from '../../api/client/base';

export function openPrototypeInNewTab(content: Record<string, unknown>) {
  const previewUrl = content.preview_url as string | undefined;

  if (previewUrl) {
    // 本地相对路径 → 拼接 API base（开发模式经过 Vite proxy）
    const fullUrl = previewUrl.startsWith('/') ? `${API_BASE}${previewUrl}` : previewUrl;
    window.open(fullUrl, '_blank');
    return;
  }

  // 无 URL 时提示
  const buildStatus = content.build_status as string | undefined;
  if (buildStatus === 'building') {
    alert('原型正在构建中，请稍后再试。');
  } else if (buildStatus === 'failed') {
    alert('原型构建失败，请查看 AI 对话中的错误信息。');
  } else if (buildStatus === 'success') {
    alert('原型已构建成功，但部署服务未配置。请联系管理员配置存储服务，或重新触发构建。');
  } else {
    alert('暂无可预览的原型。请先完成设计阶段。');
  }
}
