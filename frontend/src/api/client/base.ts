import { quotaEvents } from '../../lib/quota-events';

export const API_BASE = import.meta.env.VITE_API_URL || '';

export interface ScanEvent {
  event: string;
  message?: string;
  content?: string;
  summary?: string;
  detail?: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export type RequestFn = <T>(path: string, options?: RequestInit & { timeout?: number }, retried?: boolean) => Promise<T>;

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(base: string): Promise<boolean> {
  if (isRefreshing && refreshPromise) return refreshPromise;

  isRefreshing = true;
  refreshPromise = (async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    try {
      const resp = await fetch(`${base}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!resp.ok) return false;

      const data = await resp.json();
      localStorage.setItem('access_token', data.access_token);
      return true;
    } catch {
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function isTokenExpiringSoon(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp as number;
    return exp * 1000 - Date.now() < 120_000;
  } catch {
    return false;
  }
}

export function createRequestFn(base: string): RequestFn {
  async function request<T>(path: string, options?: RequestInit & { timeout?: number }, retried = false): Promise<T> {
    let token = localStorage.getItem('access_token');

    if (token && !retried && isTokenExpiringSoon(token)) {
      const refreshed = await tryRefreshToken(base);
      if (refreshed) {
        token = localStorage.getItem('access_token');
      }
    }

    const isFormData = options?.body instanceof FormData;
    const headers: Record<string, string> = isFormData ? {} : { 'Content-Type': 'application/json' };
    if (options?.headers && !(isFormData && Object.keys(options.headers).length === 0)) {
      Object.assign(headers, options.headers);
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const timeoutMs = options?.timeout ?? 120_000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const resp = await fetch(`${base}${path}`, {
        ...options,
        headers,
        signal: options?.signal || controller.signal,
      });

      if (resp.status === 401 && !retried) {
        const refreshed = await tryRefreshToken(base);
        if (refreshed) {
          return request(path, options, true);
        }
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/login';
        throw new ApiError(401, '登录已过期');
      }

      if (resp.status === 403) {
        const error = await resp.json().catch(() => ({ detail: resp.statusText }));
        const detail = typeof error.detail === 'string'
          ? error.detail
          : JSON.stringify(error.detail);
        if (detail.includes('套餐') || detail.includes('上限')) {
          quotaEvents.emit(detail);
        }
        throw new ApiError(403, detail || '无权限');
      }

      if (!resp.ok) {
        const error = await resp.json().catch(() => ({ detail: resp.statusText }));
        const detail = typeof error.detail === 'string'
          ? error.detail
          : JSON.stringify(error.detail);
        throw new ApiError(resp.status, detail || resp.statusText);
      }

      if (resp.status === 204) return undefined as T;
      return resp.json();
    } catch (err) {
      // 已是 ApiError (如 401/403/4xx/5xx) 直接抛, 不改文案
      if (err instanceof ApiError) throw err;
      // 网络层失败: 后端不可达 / 连接拒绝 / DNS / 超时 — 统一友好提示, 不暴露原始 Failed to fetch
      const isTimeout = err instanceof DOMException && err.name === 'AbortError';
      const detail = isTimeout
        ? '请求超时, 后端服务可能过载或不可达, 请稍后重试'
        : '无法连接后端服务, 请确认服务已启动或检查网络';
      throw new ApiError(0, detail);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return request;
}
