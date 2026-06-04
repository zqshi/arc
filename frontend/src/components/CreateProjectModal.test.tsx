import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CreateProjectModal from './CreateProjectModal';

// FolderPicker 依赖 API，mock 掉
vi.mock('../api/client', () => ({
  api: {
    browseDirectory: vi.fn().mockResolvedValue({ current: '/home', parent: '/', dirs: [] }),
    createDirectory: vi.fn().mockResolvedValue({}),
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
      }));
    });
  });
});
