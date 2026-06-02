/**
 * useDomainModelReview — 评审反馈 + 历史快照 + 评审状态的统一管理。
 *
 * 评审状态判断逻辑：
 * - none: 从未评审过（无 feedbacks 且无缓存结果）
 * - reviewed: 已评审且模型版本未变
 * - stale: 已评审但模型版本已升级，需要重新评审
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../api/client';
import type { ReviewFeedback, DomainModelSnapshot, DomainModelValidation } from '../types/api';

export type ReviewState = 'none' | 'reviewed' | 'stale';

export function useDomainModelReview(projectId: string | undefined, currentModelVersion: number = 0) {
  const [feedbacks, setFeedbacks] = useState<ReviewFeedback[]>([]);
  const [snapshots, setSnapshots] = useState<DomainModelSnapshot[]>([]);
  const [feedbacksLoading, setFeedbacksLoading] = useState(false);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [lastValidation, setLastValidation] = useState<DomainModelValidation | null>(null);
  const [validating, setValidating] = useState(false);
  const [showValidation, setShowValidation] = useState(false);

  // ── 数据加载 ──────────────────────────────────────

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

  useEffect(() => {
    loadFeedbacks();
    loadSnapshots();
  }, [loadFeedbacks, loadSnapshots]);

  // ── 评审状态推导 ──────────────────────────────────

  const lastReviewedVersion = useMemo(() => {
    if (feedbacks.length === 0) return 0;
    return Math.max(...feedbacks.map(f => f.model_version));
  }, [feedbacks]);

  const reviewState: ReviewState = useMemo(() => {
    if (feedbacks.length === 0 && !lastValidation) return 'none';
    if (currentModelVersion > lastReviewedVersion && lastReviewedVersion > 0) return 'stale';
    if (feedbacks.length > 0 || lastValidation) return 'reviewed';
    return 'none';
  }, [feedbacks.length, lastValidation, currentModelVersion, lastReviewedVersion]);

  // 从 feedbacks 反向构造展示用的 validation 摘要（当 lastValidation 丢失时兜底）
  const derivedValidation = useMemo((): DomainModelValidation | null => {
    if (feedbacks.length === 0) return null;
    const latestFeedbacks = feedbacks.filter(f => f.model_version === lastReviewedVersion);
    const errors = latestFeedbacks.filter(f => f.issue.severity === 'error').length;
    const warnings = latestFeedbacks.filter(f => f.issue.severity === 'warning').length;
    const score = Math.max(0, 100 - errors * 20 - warnings * 5);
    const level = score >= 80 ? 'good' : score >= 60 ? 'needs_improvement' : 'poor';
    return {
      score,
      level: level as DomainModelValidation['level'],
      issues: latestFeedbacks.map(f => f.issue),
      strengths: [],
      summary: `基于 ${latestFeedbacks.length} 条评审反馈重建 (v${lastReviewedVersion})`,
    };
  }, [feedbacks, lastReviewedVersion]);

  // 实际用于展示的 validation：优先用完整结果，降级用 feedbacks 推导
  const effectiveValidation = lastValidation || derivedValidation;

  // ── 评审操作 ──────────────────────────────────────

  const validate = useCallback(async () => {
    if (!projectId) return;
    setValidating(true);
    try {
      const result = await api.validateDomainModel(projectId);
      setLastValidation(result);
      setShowValidation(true);
      await loadFeedbacks();
    } catch (e) {
      console.error('Validation failed:', e);
    } finally {
      setValidating(false);
    }
  }, [projectId, loadFeedbacks]);

  const openValidation = useCallback(() => setShowValidation(true), []);
  const closeValidation = useCallback(() => setShowValidation(false), []);

  // ── 反馈处理 ──────────────────────────────────────

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

  return {
    feedbacks,
    snapshots,
    feedbacksLoading,
    snapshotsLoading,
    reviewState,
    lastReviewedVersion,
    lastValidation: effectiveValidation,
    validating,
    showValidation,
    validate,
    openValidation,
    closeValidation,
    resolveFeedback,
    rollbackModel,
    refreshFeedbacks: loadFeedbacks,
    refreshSnapshots: loadSnapshots,
  };
}
