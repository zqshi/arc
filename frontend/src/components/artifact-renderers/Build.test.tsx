import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Build from './Build';

describe('Build renderer (v6.9 artifact⑤ — BINARY_APP 构建产物锚点)', () => {
  it('renders success status badge + build target/path', () => {
    render(
      <Build
        content={{
          build_status: 'success',
          build_target: 'tauri_linux',
          artifact_path: 'dist',
        }}
      />,
    );
    expect(screen.getByText('构建成功')).toBeInTheDocument();
    expect(screen.getByText('tauri_linux')).toBeInTheDocument();
    expect(screen.getByText('dist')).toBeInTheDocument();
  });

  it('renders failed status badge', () => {
    render(<Build content={{ build_status: 'failed' }} />);
    expect(screen.getByText('构建失败')).toBeInTheDocument();
  });

  it('renders unknown status when build_status missing', () => {
    render(<Build content={{}} />);
    expect(screen.getByText('未知状态')).toBeInTheDocument();
  });
});
