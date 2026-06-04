import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConfirmDialog from './ConfirmDialog';

describe('ConfirmDialog', () => {
  const baseProps = {
    open: true,
    title: '确认操作',
    message: '你确定要执行吗？',
    onConfirm: () => {},
    onCancel: () => {},
  };

  it('renders nothing when closed', () => {
    const { container } = render(<ConfirmDialog {...baseProps} open={false} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders title and message when open', () => {
    render(<ConfirmDialog {...baseProps} />);
    expect(screen.getByText('确认操作')).toBeInTheDocument();
    expect(screen.getByText('你确定要执行吗？')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button clicked', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...baseProps} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByText('确认'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...baseProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByText('取消'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows warning variant with AlertTriangle icon', () => {
    render(<ConfirmDialog {...baseProps} variant="warning" />);
    // warning variant uses amber color confirm button
    const confirmBtn = screen.getByText('确认');
    expect(confirmBtn.className).toContain('amber');
  });

  it('uses custom button labels', () => {
    render(<ConfirmDialog {...baseProps} confirmLabel="删除" cancelLabel="返回" />);
    expect(screen.getByText('删除')).toBeInTheDocument();
    expect(screen.getByText('返回')).toBeInTheDocument();
  });

  it('disables buttons when loading', () => {
    render(<ConfirmDialog {...baseProps} loading={true} />);
    const confirmBtn = screen.getByText('确认');
    expect(confirmBtn).toBeDisabled();
  });
});
