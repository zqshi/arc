import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import type { DomainModel, BaasStatus } from '../types/api';

export function useDomainModel(projectId: string | undefined, activeTab: string) {
  const [domainModel, setDomainModel] = useState<DomainModel | null>(null);
  const [domainModelLoading, setDomainModelLoading] = useState(false);
  const [baasStatus, setBaasStatus] = useState<BaasStatus | null>(null);
  const hasFetched = useRef(false);

  const fetchDomainModel = useCallback(async (options?: { silent?: boolean }) => {
    if (!projectId) return;
    // 已有数据时静默刷新，不显示 loading（避免切 tab 闪烁）
    if (!options?.silent && !hasFetched.current) {
      setDomainModelLoading(true);
    }
    try {
      // 领域模型 + BaaS provision 状态并行拉取 (baas 失败不阻断模型展示)
      const [dm, baas] = await Promise.all([
        api.getDomainModel(projectId),
        api.getBaasStatus(projectId).catch(() => null),
      ]);
      setDomainModel(dm);
      setBaasStatus(baas);
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

  return { domainModel, domainModelLoading, fetchDomainModel, baasStatus };
}
