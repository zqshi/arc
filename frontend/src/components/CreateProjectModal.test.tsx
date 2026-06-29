import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CreateProjectModal from './CreateProjectModal';

// FolderPicker 依赖 API，mock 掉; 同时 mock 构建目标就绪查询 (v6.19 T11)
vi.mock('../api/client', () => ({
  api: {
    browseDirectory: vi.fn().mockResolvedValue({ current: '/home', parent: '/', dirs: [] }),
    createDirectory: vi.fn().mockResolvedValue({}),
    getBuildTargetReadiness: vi.fn().mockResolvedValue([
      { target: 'tauri_linux', ready: true, reason: '', verified: null },
      { target: 'web', ready: true, reason: '', verified: null },
      { target: 'capacitor_apk', ready: true, reason: '', verified: null },
      { target: 'tauri_windows', ready: false, reason: '未配置 GitHub Actions 凭证 (ARC_GHA_TOKEN)', verified: null },
      { target: 'capacitor_ios', ready: false, reason: '未配置 GitHub Actions 凭证 (ARC_GHA_TOKEN)', verified: null },
      { target: 'harmony_hap', ready: false, reason: '需自建平台 runner/工具链 (DevEco CLT)', verified: null },
    ]),
  },
}));

function renderModal(props = {}) {
  const defaultProps = {
    onClose: vi.fn(),
    onCreate: vi.fn().mockResolvedValue(undefined),
    ...props,
  };
  return render(
    <MemoryRouter>
      <CreateProjectModal {...defaultProps} />
    </MemoryRouter>
  );
}

describe('CreateProjectModal', () => {
  it('renders step 1 with name input', () => {
    renderModal();
    expect(screen.getByPlaceholderText('例如：Arc 工作台')).toBeInTheDocument();
  });

  it('disables next button when name is empty', () => {
    renderModal();
    const nextBtn = screen.getByText('下一步');
    expect(nextBtn).toBeDisabled();
  });

  it('enables next button when name is filled', () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '测试项目' } });
    const nextBtn = screen.getByText('下一步');
    expect(nextBtn).not.toBeDisabled();
  });

  it('navigates to step 2 on next click', () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '测试项目' } });
    fireEvent.click(screen.getByText('下一步'));
    expect(screen.getByText('选择工作区')).toBeInTheDocument();
    expect(screen.getByText('快速开始')).toBeInTheDocument();
  });

  it('shows three workspace options', () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: 'test' } });
    fireEvent.click(screen.getByText('下一步'));
    expect(screen.getByText('快速开始')).toBeInTheDocument();
    expect(screen.getByText('关联本地目录')).toBeInTheDocument();
    expect(screen.getByText('从 GitHub 克隆')).toBeInTheDocument();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    renderModal({ onClose });
    fireEvent.click(screen.getByText('取消'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onCreate with temporary workspace by default', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    renderModal({ onCreate });
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '新项目' } });
    fireEvent.click(screen.getByText('下一步'));
    fireEvent.click(screen.getByText('创建项目'));
    // Wait for async
    await vi.waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
        name: '新项目',
        workspace_type: 'temporary',
        project_type: 'static_site',
      }));
    });
  });

  it('allows selecting binary_app project type', async () => {
    // v6.0: binary_app 选择器放开, 默认 static_site, 可切到 binary_app
    const onCreate = vi.fn().mockResolvedValue(undefined);
    renderModal({ onCreate });
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '原生应用' } });
    fireEvent.click(screen.getByText('原生客户端'));
    fireEvent.click(screen.getByText('下一步'));
    fireEvent.click(screen.getByText('创建项目'));
    await vi.waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
        name: '原生应用',
        project_type: 'binary_app',
      }));
    });
  });

  it('shows six build targets including native platforms', async () => {
    // v6.19 T11: binary_app 透出 6 个构建目标 (linux/web/apk + windows/ios/鸿蒙)
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '原生应用' } });
    fireEvent.click(screen.getByText('原生客户端'));
    await vi.waitFor(() => {
      expect(screen.getByText('Linux 桌面')).toBeInTheDocument();
    });
    expect(screen.getByText('Windows')).toBeInTheDocument();
    expect(screen.getByText('iOS')).toBeInTheDocument();
    expect(screen.getByText('鸿蒙')).toBeInTheDocument();
  });

  it('disables unready build targets and shows reason', async () => {
    // v6.19 T11 方案3: 未就绪目标灰显 disabled + 标注原因; 就绪目标可选
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('例如：Arc 工作台'), { target: { value: '原生应用' } });
    fireEvent.click(screen.getByText('原生客户端'));
    await vi.waitFor(() => {
      expect(screen.getByText(/需自建平台 runner/)).toBeInTheDocument();
    });
    expect(screen.getByText('Windows').closest('button')).toBeDisabled();
    expect(screen.getByText('鸿蒙').closest('button')).toBeDisabled();
    // docker target 就绪, 可选
    expect(screen.getByText('Linux 桌面').closest('button')).not.toBeDisabled();
  });
});
