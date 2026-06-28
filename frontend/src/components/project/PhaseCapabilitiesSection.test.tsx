import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ToastProvider } from '../Toast';
import { PhaseCapabilitiesSection } from './PhaseCapabilitiesSection';
import { api } from '../../api/client';
import type { Capability } from '../../types/api';

vi.mock('../../api/client', () => ({
  api: {
    listCapabilities: vi.fn(),
    updatePhaseCapabilities: vi.fn(),
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
];

function renderSection(phaseCapabilities: Record<string, string[]> = {}) {
  return render(
    <ToastProvider>
      <PhaseCapabilitiesSection
        projectId="p1"
        phaseCapabilities={phaseCapabilities}
        onRefresh={vi.fn()}
      />
    </ToastProvider>,
  );
}

// 每个能力在 7 个 phase 下各渲染一次 (每 phase 独立勾选)。取首个 phase (clarification) 的按钮。
function firstCapButton() {
  return screen.getAllByText('code-reviewer')[0];
}

function expand() {
  fireEvent.click(screen.getByRole('button', { name: /环节能力配置/ }));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listCapabilities).mockResolvedValue(mockCaps);
  vi.mocked(api.updatePhaseCapabilities).mockResolvedValue({ phase_capabilities: {} });
});

describe('PhaseCapabilitiesSection', () => {
  it('renders all 7 phases with capability repeated per phase', async () => {
    renderSection();
    expand();
    await waitFor(() => expect(screen.getAllByText('code-reviewer')).toHaveLength(7));
    expect(screen.getByText('需求澄清')).toBeInTheDocument();
    expect(screen.getByText('经验抽取')).toBeInTheDocument();
  });

  it('shows empty hint when no capabilities available', async () => {
    vi.mocked(api.listCapabilities).mockResolvedValue([]);
    renderSection();
    expand();
    await waitFor(() => expect(screen.getByText(/暂无可用能力/)).toBeInTheDocument());
  });

  it('toggles capability on and calls updatePhaseCapabilities', async () => {
    renderSection();
    expand();
    await waitFor(() => expect(screen.getAllByText('code-reviewer')).toHaveLength(7));
    fireEvent.click(firstCapButton());
    await waitFor(() =>
      expect(api.updatePhaseCapabilities).toHaveBeenCalledWith('p1', 'clarification', ['c1']),
    );
  });

  it('toggles capability off when already selected', async () => {
    renderSection({ clarification: ['c1'] });
    expand();
    await waitFor(() => expect(screen.getAllByText('code-reviewer')).toHaveLength(7));
    fireEvent.click(firstCapButton());
    await waitFor(() =>
      expect(api.updatePhaseCapabilities).toHaveBeenCalledWith('p1', 'clarification', []),
    );
  });

  it('shows error toast and rolls back on failure', async () => {
    vi.mocked(api.updatePhaseCapabilities).mockRejectedValue(new Error('boom'));
    renderSection();
    expand();
    await waitFor(() => expect(screen.getAllByText('code-reviewer')).toHaveLength(7));
    fireEvent.click(firstCapButton());
    await waitFor(() => expect(screen.getByText('保存失败')).toBeInTheDocument());
    // 回滚后再次点击仍发 ['c1'] (非 ['c1','c1'])
    fireEvent.click(firstCapButton());
    await waitFor(() =>
      expect(api.updatePhaseCapabilities).toHaveBeenLastCalledWith('p1', 'clarification', ['c1']),
    );
  });

  it('is collapsed by default and expands on toggle click', async () => {
    renderSection();
    expect(screen.queryByText('需求澄清')).not.toBeInTheDocument();
    expand();
    await waitFor(() => expect(screen.getAllByText('code-reviewer')).toHaveLength(7));
  });
});
