import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface ProjectInfo {
  id: string;
  name: string;
}

interface CurrentProjectContextValue {
  project: ProjectInfo | null;
  setProject: (p: ProjectInfo | null) => void;
}

const CurrentProjectContext = createContext<CurrentProjectContextValue>({
  project: null,
  setProject: () => {},
});

export function CurrentProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProjectState] = useState<ProjectInfo | null>(null);
  const setProject = useCallback((p: ProjectInfo | null) => setProjectState(p), []);

  return (
    <CurrentProjectContext.Provider value={{ project, setProject }}>
      {children}
    </CurrentProjectContext.Provider>
  );
}

export function useCurrentProject() {
  return useContext(CurrentProjectContext);
}
