import { describe, it, expect } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import ArtifactRenderer from './index';

// ArtifactRenderer 已改为 lazy()+Suspense 自包含(v6.6 T2)。
// 测试验证两条路径: 未知类型走 CodeBlock 回退; 已知类型 lazy 渲染不崩且内容确实挂载。
describe('ArtifactRenderer', () => {
  it('未知类型走回退分支, 渲染提示 + 序列化内容', () => {
    const { container } = render(
      <ArtifactRenderer artifactType={'unknown_type' as never} content={{ foo: 'bar' } as never} />,
    );

    expect(container.textContent).toContain('未知产出物类型: unknown_type');
    // asString 对 object 走 JSON.stringify(v2 缩进)
    expect(container.textContent).toContain('"foo": "bar"');
  });

  it('未知类型 + string content 原样展示', () => {
    const { container } = render(
      <ArtifactRenderer artifactType={'unknown_type' as never} content={'plain text' as never} />,
    );

    expect(container.textContent).toContain('未知产出物类型: unknown_type');
    expect(container.textContent).toContain('plain text');
  });

  it('已知类型 lazy 加载后内容确实渲染(验证 Suspense 不阻断)', async () => {
    // Prototype renderer 读 content.preview_url 渲染为链接, URL 落在 href 而非 textContent
    const { container } = render(
      <ArtifactRenderer artifactType="prototype" content={{ preview_url: 'https://demo.arc.dev' } as never} />,
    );

    // lazy chunk 解析后内容挂载; waitFor 跨 Suspense 边界
    await waitFor(() => {
      const link = container.querySelector('a[href="https://demo.arc.dev"]');
      expect(link).toBeTruthy();
      expect(link?.getAttribute('target')).toBe('_blank');
    });
  });

  it('null content 在回退路径序列化为空串不崩', () => {
    const { container } = render(
      <ArtifactRenderer artifactType={'unknown_type' as never} content={null as never} />,
    );

    expect(container.textContent).toContain('未知产出物类型: unknown_type');
    expect(container.textContent?.replace(/\s/g, '')).not.toContain('null');
  });
});
