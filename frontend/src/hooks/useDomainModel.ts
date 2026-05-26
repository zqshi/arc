import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { DomainModel } from '../types/api';

export function useDomainModel(projectId: string | undefined, activeTab: string) {
  const [domainModel, setDomainModel] = useState<DomainModel | null>(null);
  const [domainModelLoading, setDomainModelLoading] = useState(false);

  const fetchDomainModel = useCallback(async () => {
    if (!projectId) return;
    setDomainModelLoading(true);
    try {
      const dm = await api.getDomainModel(projectId);
      setDomainModel(dm);
    } catch {
      setDomainModel(null);
    } finally {
      setDomainModelLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (activeTab === 'domain_model') { fetchDomainModel(); }
  }, [activeTab, fetchDomainModel]);

  return { domainModel, domainModelLoading, fetchDomainModel };
}
