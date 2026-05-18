import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import LoadingBar from './LoadingBar';
import { CurrentProjectProvider } from '../contexts/CurrentProjectContext';
import { useBreakpoint } from '../hooks/useMediaQuery';

export default function Layout() {
  const { isCompact } = useBreakpoint();

  return (
    <CurrentProjectProvider>
      <LoadingBar />
      <div className={`flex h-screen w-screen overflow-hidden bg-bg-primary ${isCompact ? 'flex-col' : ''}`}>
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </CurrentProjectProvider>
  );
}
