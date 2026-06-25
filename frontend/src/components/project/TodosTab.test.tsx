import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TodosTab } from './TodosTab';
import type { Version, VersionType } from '../../types/api';

function makeVersion(id: string, status: Version['status'] = 'active'): Version {
  return {
    id, project_id: 'p1', name: id, goal: '迭代目标', status,
    parent_version_id: null, order: 0, changelog: '', prototype_preview_url: '',
    created_at: '', updated_at: '',
  };
}

function makeProps(overrides: Record<string, unknown> = {}) {
  return {
    projectId: 'p1',
    versions: [makeVersion('v1')],
    versionTodos: { v1: [] },
    expandedVersions: new Set<string>(),
    toggleVersion: vi.fn(),
    versionForm: {
      show: false,
      setShow: vi.fn(),
      name: '',
      setName: vi.fn(),
      goal: '',
      setGoal: vi.fn(),
      type: 'minor' as VersionType,
      setType: vi.fn(),
      create: vi.fn(),
    },
    versionActions: {
      activate: vi.fn(),
      release: vi.fn(),
      remove: vi.fn(),
      analyze: vi.fn(),
      setCreateForVersion: vi.fn(),
    },
    todoActions: {
      delete: vi.fn(),
      resume: vi.fn(),
      complete: vi.fn(),
      reopen: vi.fn(),
    },
    navigate: vi.fn(),
    onRefreshData: vi.fn(),
    executionMode: 'pipeline' as const,
    canWrite: true,
    ...overrides,
  };
}

function renderTab(props = makeProps()) {
  return render(
    <MemoryRouter>
      <TodosTab {...(props as any)} />
    </MemoryRouter>
  );
}

describe('TodosTab', () => {
  it('renders version list with version name', () => {
    renderTab();
    expect(screen.getByText('v1')).toBeInTheDocument();
  });

  it('shows new version form when versionForm.show is true', () => {
    const props = makeProps();
    props.versionForm.show = true;
    renderTab(props);
    expect(screen.getByPlaceholderText('版本目标（一句话描述本迭代要做什么）')).toBeInTheDocument();
  });

  it('calls versionForm.setShow(true) when clicking new version button', () => {
    const setShow = vi.fn();
    const props = makeProps();
    props.versionForm.setShow = setShow;
    renderTab(props);
    fireEvent.click(screen.getByText('新版本'));
    expect(setShow).toHaveBeenCalledWith(true);
  });

  it('calls versionForm.create when clicking create button in form', () => {
    const create = vi.fn();
    const props = makeProps();
    props.versionForm.show = true;
    props.versionForm.create = create;
    renderTab(props);
    fireEvent.click(screen.getByText('创建'));
    expect(create).toHaveBeenCalledOnce();
  });
});
