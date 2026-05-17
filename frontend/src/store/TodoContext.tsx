import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import { todos as mockTodos } from '../data/mock';
import type { Todo, CreateTodoRequest } from '../types/api';

function mockToApiTodo(mock: (typeof mockTodos)[number]): Todo {
  return {
    id: mock.id,
    title: mock.title,
    description: mock.description,
    status: mock.status,
    current_phase: mock.current_phase,
    tags: mock.tags,
    created_at: mock.createdAt,
    updated_at: mock.createdAt,
  };
}

interface TodoContextValue {
  todos: Todo[];
  loading: boolean;
  error: string | null;
  addTodo: (title: string, description: string) => Promise<Todo>;
  refreshTodos: () => Promise<void>;
}

const TodoContext = createContext<TodoContextValue | null>(null);

export function TodoProvider({ children }: { children: ReactNode }) {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingMock, setUsingMock] = useState(false);

  const fetchTodos = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.listTodos();
      setTodos(data);
      setUsingMock(false);
    } catch {
      console.warn('[TodoContext] API unavailable, using mock data');
      setTodos(mockTodos.map(mockToApiTodo));
      setUsingMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTodos();
  }, [fetchTodos]);

  const addTodo = useCallback(
    async (title: string, description: string): Promise<Todo> => {
      const request: CreateTodoRequest = { title, description };

      try {
        if (usingMock) {
          throw new Error('mock mode');
        }
        const created = await api.createTodo(request);
        setTodos((prev) => [created, ...prev]);
        api.extractTags(created.id).then((updated) => {
          setTodos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
        }).catch(() => {});
        return created;
      } catch {
        const localTodo: Todo = {
          id: String(Date.now()),
          title,
          description,
          status: 'pending',
          current_phase: null,
          tags: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setTodos((prev) => [localTodo, ...prev]);
        return localTodo;
      }
    },
    [usingMock],
  );

  return (
    <TodoContext.Provider value={{ todos, loading, error, addTodo, refreshTodos: fetchTodos }}>
      {children}
    </TodoContext.Provider>
  );
}

export function useTodos() {
  const ctx = useContext(TodoContext);
  if (!ctx) throw new Error('useTodos must be used within TodoProvider');
  return ctx;
}
