import { Link, useLocation } from 'react-router-dom';
import { ListChecks, Lightbulb, Settings } from 'lucide-react';

const navItems = [
  { to: '/', icon: ListChecks, label: '任务' },
  { to: '/experience', icon: Lightbulb, label: '经验' },
];

export default function Sidebar() {
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname.startsWith('/todo');
    }
    return location.pathname.startsWith(path);
  };

  return (
    <aside className="flex w-14 flex-col items-center border-r border-border bg-bg-sidebar py-3">
      {/* Logo */}
      <Link
        to="/"
        className="mb-6 flex h-8 w-8 items-center justify-center rounded-md font-heading text-base font-bold text-accent"
      >
        A
      </Link>

      {/* Nav icons */}
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
      </nav>

      {/* Settings at bottom */}
      <Link
        to="#"
        title="设置"
        className="flex h-9 w-9 items-center justify-center rounded-md text-text-tertiary transition-colors hover:bg-accent-subtle hover:text-text-secondary"
      >
        <Settings size={18} strokeWidth={1.8} />
      </Link>
    </aside>
  );
}
