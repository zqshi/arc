import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { Experience, ExperienceCategory } from '../types/api';

export function useExperiences(projectId: string | undefined, activeTab: string) {
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [expFilter, setExpFilter] = useState<'all' | 'draft' | 'confirmed'>('all');
  const [expCategoryFilter, setExpCategoryFilter] = useState<ExperienceCategory | 'all'>('all');
  const [expLoading, setExpLoading] = useState(false);
  const [insights, setInsights] = useState<Array<{ id: string; title: string; solution: string; confidence: number; reuse_count: number }>>([]);

  const fetchExperiences = useCallback(async () => {
    if (!projectId) return;
    setExpLoading(true);
    try {
      const status = expFilter === 'all' ? undefined : expFilter;
      const category = expCategoryFilter === 'all' ? undefined : expCategoryFilter;
      const exps = await api.listProjectExperiences(projectId, { status, category });
      setExperiences(exps);
    } catch {
      setExperiences([]);
    } finally {
      setExpLoading(false);
    }
  }, [projectId, expFilter, expCategoryFilter]);

  const fetchInsights = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await api.getProjectExperienceInsights(projectId);
      setInsights(data.suggestions);
    } catch {
      setInsights([]);
    }
  }, [projectId]);

  useEffect(() => {
    if (activeTab === 'experiences') { fetchExperiences(); }
  }, [activeTab, fetchExperiences]);

  useEffect(() => {
    if (activeTab === 'settings') { fetchInsights(); }
  }, [activeTab, fetchInsights]);

  return {
    experiences, expLoading, expFilter, setExpFilter,
    expCategoryFilter, setExpCategoryFilter,
    insights, fetchExperiences,
  };
}
