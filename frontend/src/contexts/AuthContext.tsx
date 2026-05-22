import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

interface AuthUser {
  id: string;
  username: string | null;
  phone: string | null;
  display_name: string;
  role: 'admin' | 'member' | 'viewer';
}

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  login: (accessToken: string, refreshToken: string, user: AuthUser) => void;
  logout: () => void;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const storedUser = localStorage.getItem('auth_user');
    if (token && storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('auth_user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback((accessToken: string, refreshToken: string, u: AuthUser) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    localStorage.setItem('auth_user', JSON.stringify(u));
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('auth_user');
    setUser(null);
  }, []);

  const getAccessToken = useCallback(() => {
    return localStorage.getItem('access_token');
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
