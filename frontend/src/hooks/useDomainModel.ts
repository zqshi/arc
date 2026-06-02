import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import type { DomainModel } from '../types/api';

export function useDomainModel(projectId: string | undefined, activeTab: string) {
  const [domainModel, setDomainModel] = useState<DomainModel | null>(null);
  const [domainModelLoading, setDomainModelLoading] = useState(false);
  const hasFetched = useRef(false);

  const fetchDomainModel = useCallback(async (options?: { silent?: boolean }) => {
    if (!projectId) return;
    // 已有数据时静默刷新，不显示 loading（避免切 tab 闪烁）
    if (!options?.silent && !hasFetched.current) {
      setDomainModelLoading(true);
    }
    try {
      const dm = await api.getDomainModel(projectId);
      setDomainModel(dm);
      hasFetched.current = true;
    } catch {
      if (!hasFetched.current) {
        setDomainModel(null);
      }
    } finally {
      setDomainModelLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (activeTab === 'domain_model') {
      // 已有数据时静默刷新
      fetchDomainModel({ silent: hasFetched.current });
    }
  }, [activeTab, fetchDomainModel]);

  return { domainModel, domainModelLoading, fetchDomainModel };
}
