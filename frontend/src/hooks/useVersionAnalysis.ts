import { useState } from 'react';
import { api } from '../api/client';
import type { Version } from '../types/api';

interface AnalysisState {
  analysisResult: string | null;
  analyzing: boolean;
  analysisCached: boolean;
  analysisSuggestions: Array<{ priority: string; action: string; reason: string }>;
}

/**
 * 版本迭代分析 UI 状态 + 操作。
 */
export function useVersionAnalysis(
  projectId: string | undefined,
  versions: Version[],
  setVersions: React.Dispatch<React.SetStateAction<Version[]>>,
  toast: (msg: string, type?: string) => void,
) {
  const [state, setState] = useState<AnalysisState>({
    analysisResult: null,
    analyzing: false,
    analysisCached: false,
    analysisSuggestions: [],
  });

  const handleAnalyzeVersion = async (versionId: string) => {
    if (!projectId) return;
    setState({ analysisResult: null, analyzing: true, analysisCached: false, analysisSuggestions: [] });
    try {
      const targetVersion = versions.find((v) => v.id === versionId);
      const canReadCache = targetVersion?.has_analysis && !targetVersion?.analysis_stale;

      let result;
      if (canReadCache) {
        result = await api.getAnalysis(projectId, versionId);
      } else {
        result = await api.analyzeIteration(projectId, versionId);
      }

      setState({
        analysisResult: result.analysis,
        analyzing: false,
        analysisCached: result.cached ?? canReadCache ?? false,
        analysisSuggestions: result.suggestions ?? [],
      });

      // 新生成时刷新 versions 列表让按钮状态更新
      if (!canReadCache && !result.cached) {
        const v = await api.listVersions(projectId);
        setVersions(v);
      }
    } catch (err) {
      toast(`分析失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
      setState((s) => ({ ...s, analyzing: false }));
    }
  };

  const closeAnalysis = () => {
    setState({ analysisResult: null, analyzing: false, analysisCached: false, analysisSuggestions: [] });
  };

  return {
    ...state,
    handleAnalyzeVersion,
    closeAnalysis,
  };
}
