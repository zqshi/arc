import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('ApiClient', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    localStorage.clear();
    vi.resetModules();
  });

  it('attaches Authorization header when token exists', async () => {
    localStorage.setItem('access_token', 'test-token');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    });
    globalThis.fetch = mockFetch;

    const { api } = await import('../api/client');
    await api.listProjects();

    expect(mockFetch).toHaveBeenCalled();
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers['Authorization']).toBe('Bearer test-token');
  });

  it('throws on non-200 response', async () => {
    localStorage.setItem('access_token', 'valid');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: () => Promise.resolve({ detail: '权限不足' }),
    });
    globalThis.fetch = mockFetch;

    const { api } = await import('../api/client');
    await expect(api.listProjects()).rejects.toThrow('权限不足');
  });

  it('returns undefined for 204 responses', async () => {
    localStorage.setItem('access_token', 'valid');

    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    globalThis.fetch = mockFetch;

    const { api } = await import('../api/client');
    const result = await api.deleteTodo('some-id');
    expect(result).toBeUndefined();
  });
});
