import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = import.meta.env.VITE_API_URL || '';

type TabType = 'password' | 'sms';
type ModeType = 'login' | 'register';

function fetchWithTimeout(url: string, options: RequestInit, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

export default function LoginPage() {
  const { login, user } = useAuth();
  const [tab, setTab] = useState<TabType>('password');
  const [mode, setMode] = useState<ModeType>('login');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [smsSent, setSmsSent] = useState(false);
  const [smsCountdown, setSmsCountdown] = useState(0);

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const url = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login'
        ? { username, password }
        : { username, password, display_name: displayName || undefined };

      const resp = await fetchWithTimeout(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || '操作失败');
        return;
      }

      login(data.access_token, data.refresh_token, data.user);
    } catch (err) {
      setError(err instanceof DOMException && err.name === 'AbortError'
        ? '请求超时，请检查后端服务是否启动'
        : '网络错误，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  }

  async function handleSendCode() {
    if (smsCountdown > 0) return;
    setError('');

    try {
      const resp = await fetchWithTimeout(`${API_BASE}/api/auth/sms/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      });

      if (!resp.ok) {
        const data = await resp.json();
        setError(data.detail || '发送失败');
        return;
      }

      setSmsSent(true);
      setSmsCountdown(60);
      const timer = setInterval(() => {
        setSmsCountdown(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch {
      setError('发送失败，请检查后端服务');
    }
  }

  async function handleSmsSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const resp = await fetchWithTimeout(`${API_BASE}/api/auth/sms/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, code }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || '登录失败');
        return;
      }

      login(data.access_token, data.refresh_token, data.user);
    } catch {
      setError('网络错误，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  }

  if (user) return <Navigate to="/" replace />;

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-bg-primary">
      <div className="w-full max-w-sm rounded-xl border border-border bg-bg-card p-8">
        <h1 className="mb-1 text-center text-xl font-semibold text-text-primary">Arc</h1>
        <p className="mb-6 text-center text-sm text-text-secondary">AI 驱动的研发工作台</p>

        {/* Tab 切换 */}
        <div className="mb-6 flex rounded-lg bg-bg-elevated p-1">
          <button
            onClick={() => setTab('password')}
            className={`flex-1 rounded-md py-2 text-xs font-medium transition ${
              tab === 'password'
                ? 'bg-bg-card text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            账号密码
          </button>
          <button
            onClick={() => setTab('sms')}
            className={`flex-1 rounded-md py-2 text-xs font-medium transition ${
              tab === 'sms'
                ? 'bg-bg-card text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            手机验证码
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-status-error/10 px-3 py-2 text-xs text-status-error">
            {error}
          </div>
        )}

        {tab === 'password' ? (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">用户名</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-input px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
                required
                autoComplete="username"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">密码</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-input px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
                required
                minLength={6}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>
            {mode === 'register' && (
              <div>
                <label className="mb-1 block text-xs text-text-secondary">昵称（可选）</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  className="w-full rounded-lg border border-border bg-bg-input px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
                />
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-accent py-2.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              {loading ? '处理中...' : mode === 'login' ? '登录' : '注册'}
            </button>
            <p className="text-center text-xs text-text-secondary">
              {mode === 'login' ? (
                <>还没有账号？<button type="button" onClick={() => setMode('register')} className="text-accent hover:underline">注册</button></>
              ) : (
                <>已有账号？<button type="button" onClick={() => setMode('login')} className="text-accent hover:underline">登录</button></>
              )}
            </p>
          </form>
        ) : (
          <form onSubmit={handleSmsSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">手机号</label>
              <input
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="请输入手机号"
                className="w-full rounded-lg border border-border bg-bg-input px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
                required
                pattern="^1[3-9]\d{9}$"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">验证码</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  placeholder="6位验证码"
                  maxLength={6}
                  className="flex-1 rounded-lg border border-border bg-bg-input px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
                  required
                />
                <button
                  type="button"
                  onClick={handleSendCode}
                  disabled={smsCountdown > 0 || !phone}
                  className="whitespace-nowrap rounded-lg border border-border px-3 py-2 text-xs text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {smsCountdown > 0 ? `${smsCountdown}s` : smsSent ? '重新发送' : '获取验证码'}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading || !code}
              className="w-full rounded-lg bg-accent py-2.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              {loading ? '处理中...' : '登录 / 注册'}
            </button>
            <p className="text-center text-[10px] text-text-muted">
              未注册手机号将自动创建账号
            </p>
          </form>
        )}
        <div className="mt-6 rounded-lg bg-bg-elevated p-3">
          <p className="mb-1.5 text-[10px] font-medium text-text-tertiary">测试账号</p>
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => { setTab('password'); setMode('login'); setUsername('demo'); setPassword('demo123'); }}
              className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[11px] text-text-secondary hover:bg-bg-card"
            >
              <span>demo / demo123</span>
              <span className="text-[10px] text-text-muted">点击填入</span>
            </button>
            <button
              type="button"
              onClick={() => { setTab('password'); setMode('login'); setUsername('test'); setPassword('test123'); }}
              className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[11px] text-text-secondary hover:bg-bg-card"
            >
              <span>test / test123</span>
              <span className="text-[10px] text-text-muted">点击填入</span>
            </button>
          </div>
          <p className="mt-1.5 text-[10px] text-text-muted">手机号登录验证码固定为 666666</p>
        </div>
      </div>
    </div>
  );
}
