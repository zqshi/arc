import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ActionMenu from './ActionMenu';
import type { ActionMenuItem } from './ActionMenu';

describe('ActionMenu', () => {
  it('renders nothing when items is empty', () => {
    const { container } = render(<ActionMenu items={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders trigger button when items exist', () => {
    const items: ActionMenuItem[] = [
      { label: '编辑', onClick: vi.fn() },
    ];
    render(<ActionMenu items={items} />);
    const button = screen.getByRole('button');
    expect(button).toBeTruthy();
  });

  it('shows menu on click', () => {
    const onClick = vi.fn();
    const items: ActionMenuItem[] = [
      { label: '删除', danger: true, onClick },
    ];
    render(<ActionMenu items={items} />);

    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('删除')).toBeTruthy();
  });

  it('calls onClick and closes menu on item click', () => {
    const onClick = vi.fn();
    const items: ActionMenuItem[] = [
      { label: '归档', onClick },
    ];
    render(<ActionMenu items={items} />);

    fireEvent.click(screen.getByRole('button'));  // open
    fireEvent.click(screen.getByText('归档'));     // select

    expect(onClick).toHaveBeenCalledTimes(1);
    // Menu should be closed
    expect(screen.queryByText('归档')).toBeNull();
  });

  it('applies danger styling', () => {
    const items: ActionMenuItem[] = [
      { label: '危险操作', danger: true, onClick: vi.fn() },
    ];
    render(<ActionMenu items={items} />);

    fireEvent.click(screen.getByRole('button'));
    const item = screen.getByText('危险操作');
    expect(item.className).toContain('text-status-error');
  });
});
