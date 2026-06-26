import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('CapabilityApi', () => {
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

  it('listCapabilities builds query from params', async () => {
    localStorage.setItem('access_token', 't');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve([]),
    });
    globalThis.fetch = mockFetch;
    const { api } = await import('./client');
    await api.listCapabilities({ type: 'agent', status: 'active' });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/capabilities');
    expect(url).toContain('type=agent');
    expect(url).toContain('status=active');
  });

  it('listCapabilities omits query when no params', async () => {
    localStorage.setItem('access_token', 't');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve([]),
    });
    globalThis.fetch = mockFetch;
    const { api } = await import('./client');
    await api.listCapabilities();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/capabilities');
  });

  it('createCapability POSTs body', async () => {
    localStorage.setItem('access_token', 't');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 201,
      json: () => Promise.resolve({ id: '1', name: 'n', type: 'agent', config: {}, status: 'active', scope: 'global' }),
    });
    globalThis.fetch = mockFetch;
    const { api } = await import('./client');
    const cap = await api.createCapability({ name: 'n', type: 'agent' });
    expect(cap.id).toBe('1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/capabilities');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ name: 'n', type: 'agent' });
  });

  it('updatePhaseCapabilities PUTs phase + capability_ids', async () => {
    localStorage.setItem('access_token', 't');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve({ phase_capabilities: {} }),
    });
    globalThis.fetch = mockFetch;
    const { api } = await import('./client');
    await api.updatePhaseCapabilities('pid', 'development', ['c1', 'c2']);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/projects/pid/pipeline/phase-capabilities');
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body)).toEqual({ phase: 'development', capability_ids: ['c1', 'c2'] });
  });

  it('deleteCapability returns body on 200', async () => {
    localStorage.setItem('access_token', 't');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve({ status: 'deleted', id: 'c1' }),
    });
    globalThis.fetch = mockFetch;
    const { api } = await import('./client');
    const res = await api.deleteCapability('c1');
    expect(res.status).toBe('deleted');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(opts.method).toBe('DELETE');
  });
});
