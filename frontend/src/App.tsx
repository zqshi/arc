import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import TodoList from './pages/TodoList';
import TodoDetail from './pages/TodoDetail';
import ExperienceList from './pages/ExperienceList';
import { TodoProvider } from './store/TodoContext';
import { ToastProvider } from './components/Toast';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <TodoProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<TodoList />} />
              <Route path="/todo/:id" element={<TodoDetail />} />
              <Route path="/experience" element={<ExperienceList />} />
            </Route>
          </Routes>
        </TodoProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
