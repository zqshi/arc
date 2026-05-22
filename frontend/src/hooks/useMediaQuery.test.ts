import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useMediaQuery, useBreakpoint } from '../hooks/useMediaQuery';

function mockMatchMedia(matches: boolean) {
  const listeners: Array<(e: { matches: boolean }) => void> = [];
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: (_: string, cb: (e: { matches: boolean }) => void) => listeners.push(cb),
      removeEventListener: () => {},
    })),
  });
  return listeners;
}

describe('useMediaQuery', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns true when media query matches', () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery('(min-width: 1px)'));
    expect(result.current).toBe(true);
  });

  it('returns false for non-matching query', () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery('(min-width: 99999px)'));
    expect(result.current).toBe(false);
  });
});

describe('useBreakpoint', () => {
  it('returns isCompact and isNarrow booleans', () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useBreakpoint());
    expect(typeof result.current.isCompact).toBe('boolean');
    expect(typeof result.current.isNarrow).toBe('boolean');
  });
});
