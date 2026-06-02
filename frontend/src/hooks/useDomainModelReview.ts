/**
 * useDomainModelReview — 管理领域模型评审反馈 + 历史快照的数据获取。
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { ReviewFeedback, DomainModelSnapshot } from '../types/api';

export function useDomainModelReview(projectId: string | undefined) {
  const [feedbacks, setFeedbacks] = useState<ReviewFeedback[]>([]);
  const [snapshots, setSnapshots] = useState<DomainModelSnapshot[]>([]);
  const [feedbacksLoading, setFeedbacksLoading] = useState(false);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);

  const loadFeedbacks = useCallback(async () => {
    if (!projectId) return;
    setFeedbacksLoading(true);
    try {
      const data = await api.listReviewFeedbacks(projectId);
      setFeedbacks(data);
    } catch (e) {
      console.error('Failed to load review feedbacks:', e);
    } finally {
      setFeedbacksLoading(false);
    }
  }, [projectId]);

  const loadSnapshots = useCallback(async () => {
    if (!projectId) return;
    setSnapshotsLoading(true);
    try {
      const data = await api.getDomainModelHistory(projectId);
      setSnapshots(data);
    } catch (e) {
      console.error('Failed to load model history:', e);
    } finally {
      setSnapshotsLoading(false);
    }
  }, [projectId]);

  const resolveFeedback = useCallback(async (feedbackId: string, action: string, note?: string) => {
    if (!projectId) return;
    await api.resolveReviewFeedback(projectId, feedbackId, action, note);
    await loadFeedbacks();
  }, [projectId, loadFeedbacks]);

  const rollbackModel = useCallback(async (version: number) => {
    if (!projectId) return;
    await api.rollbackDomainModel(projectId, version);
    await loadSnapshots();
  }, [projectId, loadSnapshots]);

  useEffect(() => {
    loadFeedbacks();
    loadSnapshots();
  }, [loadFeedbacks, loadSnapshots]);

  return {
    feedbacks,
    snapshots,
    feedbacksLoading,
    snapshotsLoading,
    resolveFeedback,
    rollbackModel,
    refreshFeedbacks: loadFeedbacks,
    refreshSnapshots: loadSnapshots,
  };
}
