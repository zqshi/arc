/**
 * useTheme — 主题模式管理。
 * 支持 dark / light / system 三种模式，持久化到 localStorage。
 */
import { useState, useEffect, useCallback } from 'react';

export type ThemeMode = 'dark' | 'light' | 'system';

const STORAGE_KEY = 'arc-theme';

function getInitialTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored;
  } catch {}
  return 'dark'; // 默认暗色
}

function applyTheme(mode: ThemeMode) {
  document.documentElement.setAttribute('data-theme', mode);
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(getInitialTheme);

  const setTheme = useCallback((mode: ThemeMode) => {
    setThemeState(mode);
    localStorage.setItem(STORAGE_KEY, mode);
    applyTheme(mode);
  }, []);

  // 初始化时应用主题
  useEffect(() => {
    applyTheme(theme);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // 监听系统主题变化（仅 system 模式下需要触发重渲染）
  useEffect(() => {
    if (theme !== 'system') return;

    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      // data-theme="system" 不变，CSS 媒体查询自动切换
      // 这里强制触发一次 re-render 让依赖 theme 的组件更新
      setThemeState('system');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme]);

  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  return { theme, setTheme, isDark };
}
