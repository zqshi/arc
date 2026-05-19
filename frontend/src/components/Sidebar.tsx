import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FolderOpen, Lightbulb, Settings, Menu, X, LogOut } from 'lucide-react';
import { useCurrentProject } from '../contexts/CurrentProjectContext';
import { useAuth } from '../contexts/AuthContext';
import { useBreakpoint } from '../hooks/useMediaQuery';

const navItems = [
  { to: '/', icon: FolderOpen, label: '项目' },
  { to: '/experience', icon: Lightbulb, label: '经验' },
];

function UserPopover({ user, onLogout }: { user: { display_name: string; username: string | null }; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const initial = (user.display_name || user.username || '?')[0];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        title={user.display_name || user.username || ''}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-[11px] font-medium text-accent transition-colors hover:bg-accent/25"
      >
        {initial}
      </button>
      {open && (
        <div className="absolute bottom-0 left-12 z-50 w-36 rounded-lg border border-border bg-bg-card py-1.5 shadow-xl">
          <div className="truncate px-3 py-1.5 text-[11px] font-medium text-text-primary">
            {user.display_name || user.username}
          </div>
          <div className="mx-2 my-1 h-px bg-border" />
          <button
            onClick={() => { setOpen(false); onLogout(); }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-[11px] text-status-error transition-colors hover:bg-status-error/10"
          >
            <LogOut size={13} strokeWidth={1.8} />
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { project } = useCurrentProject();
  const { user, logout } = useAuth();
  const { isCompact } = useBreakpoint();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname.startsWith('/project/') || location.pathname.startsWith('/todo');
    }
    return location.pathname.startsWith(path);
  };

  const showProjectIndicator =
    project &&
    (location.pathname.startsWith('/project/') || location.pathname.startsWith('/todo/'));

  if (isCompact) {
    return (
      <>
        <header className="flex h-11 w-full items-center justify-between border-b border-border bg-bg-sidebar px-3">
          <div className="flex items-center gap-1">
            <Link
              to="/"
              className="flex h-7 w-7 items-center justify-center rounded-md font-heading text-sm font-bold text-accent"
            >
              A
            </Link>
            {showProjectIndicator && (
              <>
                <span className="text-text-muted text-[10px]">/</span>
                <Link
                  to={`/project/${project.id}`}
                  className="rounded-md bg-accent/10 px-1.5 py-0.5 text-[10px] font-semibold text-accent"
                >
                  {project.name.slice(0, 6)}
                </Link>
              </>
            )}
          </div>
          <button
            onClick={() => setDrawerOpen(!drawerOpen)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-text-tertiary hover:bg-bg-elevated hover:text-text-secondary"
          >
            {drawerOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </header>
        {drawerOpen && (
          <>
            <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setDrawerOpen(false)} />
            <nav className="fixed right-0 top-11 z-50 w-48 rounded-bl-lg border-b border-l border-border bg-bg-sidebar p-2 shadow-xl">
              {navItems.map(({ to, icon: Icon, label }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setDrawerOpen(false)}
                  className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-xs transition-colors ${
                    isActive(to)
                      ? 'bg-accent-subtle text-accent font-medium'
                      : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  }`}
                >
                  <Icon size={15} strokeWidth={1.8} />
                  {label}
                </Link>
              ))}
              <div className="my-1.5 h-px bg-border" />
              <Link
                to="/settings"
                onClick={() => setDrawerOpen(false)}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-xs transition-colors ${
                  location.pathname === '/settings'
                    ? 'bg-accent-subtle text-accent font-medium'
                    : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                }`}
              >
                <Settings size={15} strokeWidth={1.8} />
                设置
              </Link>
              <div className="my-1.5 h-px bg-border" />
              {user && (
                <div className="px-3 py-1.5 text-[10px] text-text-muted truncate">
                  {user.display_name || user.username}
                </div>
              )}
              <button
                onClick={() => { setDrawerOpen(false); handleLogout(); }}
                className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-xs text-status-error transition-colors hover:bg-status-error/10"
              >
                <LogOut size={15} strokeWidth={1.8} />
                退出登录
              </button>
            </nav>
          </>
        )}
      </>
    );
  }

  return (
    <aside className="flex w-14 flex-col items-center border-r border-border bg-bg-sidebar py-3">
      <Link
        to="/"
        className="mb-6 flex h-8 w-8 items-center justify-center rounded-md font-heading text-base font-bold text-accent"
      >
        A
      </Link>

      <nav className="flex flex-1 flex-col items-center gap-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            title={label}
            className={`flex h-9 w-9 items-center justify-center rounded-md transition-colors ${
              isActive(to)
                ? 'bg-accent-subtle text-accent'
                : 'text-text-tertiary hover:bg-accent-subtle hover:text-text-secondary'
            }`}
          >
            <Icon size={18} strokeWidth={1.8} />
          </Link>
        ))}

        {showProjectIndicator && (
          <>
            <div className="my-1.5 h-px w-5 bg-border" />
            <Link
              to={`/project/${project.id}`}
              title={project.name}
              className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/10 text-[11px] font-semibold text-accent transition-colors hover:bg-accent/20"
            >
              {project.name.slice(0, 2)}
            </Link>
          </>
        )}
      </nav>

      <div className="flex flex-col items-center gap-1">
        <Link
          to="/settings"
          title="设置"
          className={`flex h-9 w-9 items-center justify-center rounded-md transition-colors ${
            location.pathname === '/settings'
              ? 'bg-accent-subtle text-accent'
              : 'text-text-tertiary hover:bg-accent-subtle hover:text-text-secondary'
          }`}
        >
          <Settings size={18} strokeWidth={1.8} />
        </Link>
        {user && <UserPopover user={user} onLogout={handleLogout} />}
      </div>
    </aside>
  );
}
