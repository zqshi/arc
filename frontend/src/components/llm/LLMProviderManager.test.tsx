import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LLMProviderManager } from './LLMProviderManager';
import { api } from '../../api/client';
import type { LLMProvider, ProviderTemplate } from '../../types/api';

vi.mock('../../api/client', () => ({
  api: {
    listProviders: vi.fn(),
    listProviderTemplates: vi.fn(),
    createProvider: vi.fn(),
    updateProvider: vi.fn(),
    deleteProvider: vi.fn(),
    verifyCredentials: vi.fn(),
    listModels: vi.fn(),
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

const mockTemplates: ProviderTemplate[] = [
  {
    key: 'openai', label: 'OpenAI', kind: 'openai_compatible',
    default_base_url: 'https://api.openai.com/v1',
    supports_list_models: true, suggested_models: ['gpt-4o'],
  },
  {
    key: 'anthropic', label: 'Anthropic', kind: 'anthropic',
    default_base_url: '', supports_list_models: false,
    suggested_models: ['claude-sonnet-4-6'],
  },
];

const mockProviders: LLMProvider[] = [
  {
    id: 'p1', name: '我的OpenAI', kind: 'openai_compatible',
    base_url: 'https://api.openai.com/v1', models: ['gpt-4o'],
    is_default: true, api_key_set: true,
  },
  {
    id: 'p2', name: '本地ollama', kind: 'openai_compatible',
    base_url: 'http://localhost:11434/v1', models: [],
    is_default: false, api_key_set: false,
  },
];

describe('LLMProviderManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listProviders).mockResolvedValue(mockProviders);
    vi.mocked(api.listProviderTemplates).mockResolvedValue(mockTemplates);
  });

  it('renders provider list with default badge', async () => {
    render(<LLMProviderManager />);
    await waitFor(() => expect(api.listProviders).toHaveBeenCalled());
    expect(screen.getByText('我的OpenAI')).toBeInTheDocument();
    expect(screen.getByText('默认')).toBeInTheDocument(); // p1 is_default
    expect(screen.getByText('本地ollama')).toBeInTheDocument();
  });

  it('shows add form on add button click', async () => {
    render(<LLMProviderManager />);
    await waitFor(() => expect(screen.getByText('我的OpenAI')).toBeInTheDocument());
    fireEvent.click(screen.getByText('添加 LLM 厂商'));
    expect(screen.getByText('添加凭证')).toBeInTheDocument();
    // 模板按钮可见
    expect(screen.getByText('OpenAI')).toBeInTheDocument();
    expect(screen.getByText('Anthropic')).toBeInTheDocument();
  });

  it('selecting template fills base_url', async () => {
    render(<LLMProviderManager />);
    await waitFor(() => expect(screen.getByText('我的OpenAI')).toBeInTheDocument());
    fireEvent.click(screen.getByText('添加 LLM 厂商'));
    const anthropicBtn = screen.getByText('Anthropic');
    fireEvent.click(anthropicBtn);
    // 选 anthropic 后 kind 切换, 模型清单区显示静态建议标注
    await waitFor(() => {
      expect(screen.getByText(/静态建议/)).toBeInTheDocument();
    });
  });

  it('create requires api_key', async () => {
    vi.mocked(api.createProvider).mockResolvedValue(mockProviders[0]);
    render(<LLMProviderManager />);
    await waitFor(() => expect(screen.getByText('我的OpenAI')).toBeInTheDocument());
    fireEvent.click(screen.getByText('添加 LLM 厂商'));
    fireEvent.change(screen.getByPlaceholderText('如 我的OpenAI / 国内代理'), {
      target: { value: 'test-name' },
    });
    fireEvent.click(screen.getByText('保存'));
    // 无 api_key → 提示
    await waitFor(() => {
      expect(screen.getByText('新建凭证需填写 API Key')).toBeInTheDocument();
    });
    expect(api.createProvider).not.toHaveBeenCalled();
  });

  it('deletes provider on confirm', async () => {
    vi.mocked(api.deleteProvider).mockResolvedValue({ status: 'deleted' });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<LLMProviderManager />);
    await waitFor(() => expect(screen.getByText('我的OpenAI')).toBeInTheDocument());
    const deleteButtons = screen.getAllByTitle('删除');
    fireEvent.click(deleteButtons[0]);
    await waitFor(() => expect(api.deleteProvider).toHaveBeenCalledWith('p1'));
  });

  it('calls onDefaultChanged after set default', async () => {
    vi.mocked(api.updateProvider).mockResolvedValue(mockProviders[0]);
    const onDefaultChanged = vi.fn();
    render(<LLMProviderManager onDefaultChanged={onDefaultChanged} />);
    await waitFor(() => expect(screen.getByText('本地ollama')).toBeInTheDocument());
    // p2 非 default → 有设为默认按钮
    const setDefaultButtons = screen.getAllByTitle('设为默认');
    fireEvent.click(setDefaultButtons[0]);
    await waitFor(() => expect(onDefaultChanged).toHaveBeenCalled());
  });
});
