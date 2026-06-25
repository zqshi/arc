import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SkeletonLine, SkeletonCard, ProjectListSkeleton, TodoDetailSkeleton } from './Skeleton';

describe('SkeletonLine', () => {
  it('renders a div with animate-pulse', () => {
    const { container } = render(<SkeletonLine />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('animate-pulse');
  });

  it('accepts custom className', () => {
    const { container } = render(<SkeletonLine className="h-4 w-full" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('h-4');
    expect(el.className).toContain('w-full');
  });
});

describe('SkeletonCard', () => {
  it('renders multiple skeleton lines', () => {
    const { container } = render(<SkeletonCard />);
    const lines = container.querySelectorAll('.animate-pulse');
    expect(lines.length).toBeGreaterThanOrEqual(3);
  });
});

describe('ProjectListSkeleton', () => {
  it('renders 6 skeleton cards', () => {
    const { container } = render(<ProjectListSkeleton />);
    // Each SkeletonCard has a border container
    const cards = container.querySelectorAll('.rounded-lg');
    expect(cards.length).toBe(6);
  });
});

describe('TodoDetailSkeleton', () => {
  it('renders sidebar and content area', () => {
    const { container } = render(<TodoDetailSkeleton />);
    const lines = container.querySelectorAll('.animate-pulse');
    expect(lines.length).toBeGreaterThan(5);
  });
});
