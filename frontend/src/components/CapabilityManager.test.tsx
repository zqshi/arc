import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ToastProvider } from './Toast';
import { ConfirmProvider } from './ConfirmProvider';
import { AuthProvider } from '../contexts/AuthContext';
import { CapabilityManager } from './CapabilityManager';
import { api } from '../api/client';
import type { Capability } from '../types/api';

vi.mock('../api/client', () => ({
  api: {
    listCapabilities: vi.fn(),
    createCapability: vi.fn(),
    updateCapability: vi.fn(),
    deleteCapability: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.name = 'ApiError';
      this.status = status;
      this.detail = detail;
    }
  },
}));

const mockCaps: Capability[] = [
  { id: 'c1', name: 'code-reviewer', type: 'agent', config: {}, status: 'active', scope: 'global' },
  { id: 'c2', name: 'prd-writer', type: 'skill', config: {}, status: 'disabled', scope: 'global' },
];

// AuthProvider useEffect 要求 access_token && auth_user 同时存在才加载 user
function setUser(role: 'admin' | 'member') {
  localStorage.setItem('access_token', 'dummy-token');
  localStorage.setItem(
    'auth_user',
    JSON.stringify({ id: 'u1', username: 'a', phone: null, display_name: 'A', role }),
  );
}

function renderManager(role: 'admin' | 'member' = 'admin') {
  setUser(role);
  return render(
    <AuthProvider>
      <ToastProvider>
        <ConfirmProvider>
          <CapabilityManager />
        </ConfirmProvider>
      </ToastProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  vi.mocked(api.listCapabilities).mockResolvedValue(mockCaps);
  vi.mocked(api.updateCapability).mockResolvedValue(mockCaps[0]);
  vi.mocked(api.deleteCapability).mockResolvedValue({ status: 'deleted', id: 'c1' });
});

describe('CapabilityManager', () => {
  it('loads and renders capabilities', async () => {
    renderManager();
    await waitFor(() => expect(screen.getByText('code-reviewer')).toBeInTheDocument());
    expect(screen.getByText('prd-writer')).toBeInTheDocument();
  });

  it('shows create button for admin', async () => {
    renderManager('admin');
    await waitFor(() => expect(screen.getByText('新增能力')).toBeInTheDocument());
  });

  it('hides write actions for non-admin', async () => {
    renderManager('member');
    await waitFor(() => expect(screen.getByText('code-reviewer')).toBeInTheDocument());
    expect(screen.queryByText('新增能力')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('编辑能力')).not.toBeInTheDocument();
  });

  it('toggles status on toggle click', async () => {
    renderManager('admin');
    await waitFor(() => expect(screen.getByText('code-reviewer')).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText('禁用能力'));
    await waitFor(() =>
      expect(api.updateCapability).toHaveBeenCalledWith('c1', { status: 'disabled' }),
    );
  });

  it('deletes capability after confirm', async () => {
    renderManager('admin');
    await waitFor(() => expect(screen.getByText('code-reviewer')).toBeInTheDocument());
    fireEvent.click(screen.getAllByLabelText('删除能力')[0]);
    const confirmBtn = await screen.findByRole('button', { name: '删除' });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(api.deleteCapability).toHaveBeenCalledWith('c1'));
  });
});
