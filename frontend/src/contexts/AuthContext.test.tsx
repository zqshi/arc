import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import type { ReactNode } from 'react';

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts with null user when no stored token', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('restores user from localStorage on mount', () => {
    const user = { id: '1', username: 'test', phone: null, display_name: 'Test', role: 'admin' as const };
    localStorage.setItem('access_token', 'token');
    localStorage.setItem('auth_user', JSON.stringify(user));

    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user).toEqual(user);
  });

  it('login stores tokens and sets user', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    const user = { id: '2', username: 'dev', phone: '123', display_name: 'Dev', role: 'member' as const };

    act(() => {
      result.current.login('access-tok', 'refresh-tok', user);
    });

    expect(result.current.user).toEqual(user);
    expect(localStorage.getItem('access_token')).toBe('access-tok');
    expect(localStorage.getItem('refresh_token')).toBe('refresh-tok');
  });

  it('logout clears tokens and user', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    const user = { id: '1', username: 'x', phone: null, display_name: 'X', role: 'admin' as const };

    act(() => { result.current.login('a', 'b', user); });
    act(() => { result.current.logout(); });

    expect(result.current.user).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('getAccessToken returns current token', () => {
    localStorage.setItem('access_token', 'my-token');
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.getAccessToken()).toBe('my-token');
  });
});
