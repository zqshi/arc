import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

export default function LoadingBar() {
  const location = useLocation();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    setVisible(true);
    setProgress(30);

    timer.current = setTimeout(() => setProgress(60), 100);

    const done = setTimeout(() => {
      setProgress(100);
      setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 200);
    }, 300);

    return () => {
      clearTimeout(timer.current);
      clearTimeout(done);
    };
  }, [location.pathname]);

  if (!visible) return null;

  return (
    <div className="fixed left-0 right-0 top-0 z-[100] h-0.5">
      <div
        className="h-full bg-accent transition-all duration-200 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
