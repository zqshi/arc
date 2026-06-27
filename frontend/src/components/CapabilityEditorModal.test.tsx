import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ToastProvider } from './Toast';
import { CapabilityEditorModal } from './CapabilityEditorModal';
import { api } from '../api/client';
import type { Capability } from '../types/api';

vi.mock('../api/client', () => ({
  api: {
    createCapability: vi.fn(),
    updateCapability: vi.fn(),
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

const inlineSkill: Capability = {
  id: 'c1',
  name: 'my-skill',
  type: 'skill',
  config: { source: 'inline', content: '---\nname: my-skill\n---\nbody' },
  status: 'active',
  scope: 'global',
};

function renderModal(capability?: Capability | null) {
  return render(
    <ToastProvider>
      <CapabilityEditorModal
        open
        onClose={vi.fn()}
        onSaved={vi.fn()}
        capability={capability ?? null}
      />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.createCapability).mockResolvedValue(inlineSkill);
  vi.mocked(api.updateCapability).mockResolvedValue(inlineSkill);
});

describe('CapabilityEditorModal — C3 skill 多来源', () => {
  it('switches skill source to inline and shows content textarea', () => {
    renderModal();
    fireEvent.click(screen.getByText('Skill'));
    // 默认 directory, 切 inline
    fireEvent.click(screen.getByText('内联文本'));
    expect(screen.getByPlaceholderText(/name: code-reviewer/)).toBeInTheDocument();
    // directory input 不应显示
    expect(screen.queryByPlaceholderText('例如：~/.claude/skills/code-reviewer')).not.toBeInTheDocument();
  });

  it('submits skill with inline config', async () => {
    renderModal();
    fireEvent.click(screen.getByText('Skill'));
    fireEvent.click(screen.getByText('内联文本'));
    fireEvent.change(screen.getByPlaceholderText(/name: code-reviewer/), {
      target: { value: '---\nname: x\n---\nbody' },
    });
    fireEvent.change(screen.getByPlaceholderText('例如：code-reviewer / prd-writer'), {
      target: { value: 'my-skill' },
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() =>
      expect(api.createCapability).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'skill',
          config: { source: 'inline', content: '---\nname: x\n---\nbody' },
        }),
      ),
    );
  });

  it('submits skill with directory config', async () => {
    renderModal();
    fireEvent.click(screen.getByText('Skill'));
    // 默认 directory source
    fireEvent.change(screen.getByPlaceholderText('例如：~/.claude/skills/code-reviewer'), {
      target: { value: '/path/to/skill' },
    });
    fireEvent.change(screen.getByPlaceholderText('例如：code-reviewer / prd-writer'), {
      target: { value: 'my-skill' },
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() =>
      expect(api.createCapability).toHaveBeenCalledWith(
        expect.objectContaining({
          config: { source: 'directory', directory: '/path/to/skill' },
        }),
      ),
    );
  });

  it('submits skill with empty directory = default config', async () => {
    renderModal();
    fireEvent.click(screen.getByText('Skill'));
    fireEvent.change(screen.getByPlaceholderText('例如：code-reviewer / prd-writer'), {
      target: { value: 'my-skill' },
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() =>
      expect(api.createCapability).toHaveBeenCalledWith(
        expect.objectContaining({ config: {} }),
      ),
    );
  });

  it('validates inline skill requires content', async () => {
    renderModal();
    fireEvent.click(screen.getByText('Skill'));
    fireEvent.click(screen.getByText('内联文本'));
    fireEvent.change(screen.getByPlaceholderText('例如：code-reviewer / prd-writer'), {
      target: { value: 'my-skill' },
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() =>
      expect(screen.getByText('inline skill 需填写 SKILL.md 内容')).toBeInTheDocument(),
    );
    expect(api.createCapability).not.toHaveBeenCalled();
  });

  it('loads existing inline skill on edit', async () => {
    renderModal(inlineSkill);
    await waitFor(() => expect(screen.getByDisplayValue(/name: my-skill/)).toBeInTheDocument());
    // 编辑模式 type 不可改, 但 skill source 已载入 inline → content textarea 显示, directory input 不显示
    expect(screen.queryByPlaceholderText('例如：~/.claude/skills/code-reviewer')).not.toBeInTheDocument();
  });

  it('updates inline skill preserving source/content', async () => {
    renderModal(inlineSkill);
    const contentArea = await screen.findByPlaceholderText(/name: code-reviewer/);
    fireEvent.change(contentArea, {
      target: { value: '---\nname: my-skill\n---\nnew body' },
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() =>
      expect(api.updateCapability).toHaveBeenCalledWith(
        'c1',
        expect.objectContaining({
          config: { source: 'inline', content: '---\nname: my-skill\n---\nnew body' },
        }),
      ),
    );
  });
});
