import { useState, useEffect, useRef, useCallback } from 'react';
import { ScanSearch, RefreshCw, AlertCircle, GitCompare } from 'lucide-react';
import { api } from '../../api/client';
import type { ScanEvent } from '../../api/client';

interface ScanDiff {
  type: 'initial' | 'incremental' | 'summary_only';
  aggregates_added?: string[] | number;
  aggregates_removed?: string[];
  subdomains_added?: string[] | number;
  subdomains_removed?: string[];
  contexts_added?: string[] | number;
  summary_changed?: boolean;
}

interface ScanSectionProps {
  projectId: string;
  localPath: string;
  codebaseSummary: string;
  dirty: boolean;
  initialScanStatus?: 'idle' | 'scanning' | 'completed' | 'error';
  scanProgressText?: string;
  scanErrorText?: string;
  lastScanDiff?: ScanDiff | null;
  onRefresh: () => void;
  onSummaryChange: (summary: string) => void;
}

export function ScanSection({
  projectId,
  localPath,
  codebaseSummary,
  dirty,
  initialScanStatus,
  scanProgressText,
  scanErrorText,
  lastScanDiff,
  onRefresh,
  onSummaryChange,
}: ScanSectionProps) {
  const [scanning, setScanning] = useState(initialScanStatus === 'scanning');
  const [scanStage, setScanStage] = useState(scanProgressText || '');
  const [scanContent, setScanContent] = useState('');
  const [scanError, setScanError] = useState(initialScanStatus === 'error' ? (scanErrorText || '扫描失败') : '');
  const abortRef = useRef<AbortController | null>(null);
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    if (initialScanStatus === 'completed' && scanning) {
      setScanning(false);
      setScanStage('');
    }
    if (initialScanStatus === 'error' && scanning) {
      setScanning(false);
      setScanError(scanErrorText || '扫描失败');
    }
  }, [initialScanStatus, scanErrorText]); // eslint-disable-line react-hooks/exhaustive-deps

  const subscribeToScanStream = useCallback(() => {
    setScanning(true);
    setScanError('');

    const controller = new AbortController();
    abortRef.current = controller;

    const timeout = setTimeout(() => {
      controller.abort();
      setScanError('扫描超时，请重试');
      setScanning(false);
    }, 5 * 60 * 1000);

    api.scanCodebaseStream(projectId, (event: ScanEvent) => {
      switch (event.event) {
        case 'replay':
          setScanContent(event.content || '');
          break;
        case 'stage':
          setScanStage(event.message || '');
          break;
        case 'chunk':
          setScanContent((prev) => prev + (event.content || ''));
          break;
        case 'done':
          clearTimeout(timeout);
          setScanContent(event.summary || '');
          setScanning(false);
          setScanStage('');
          onRefreshRef.current();
          break;
        case 'error':
          clearTimeout(timeout);
          setScanError(event.detail || '扫描失败');
          setScanning(false);
          setScanStage('');
          break;
        case 'close':
          clearTimeout(timeout);
          setScanning(false);
          break;
      }
    }, controller.signal);
  }, [projectId]);

  useEffect(() => {
    if (initialScanStatus === 'scanning' && projectId) {
      subscribeToScanStream();
      return () => { abortRef.current?.abort(); };
    }
    if (initialScanStatus === 'completed' && !codebaseSummary) {
      onRefreshRef.current();
    }
  }, [initialScanStatus, projectId, subscribeToScanStream]); // eslint-disable-line react-hooks/exhaustive-deps

  const startScan = useCallback(async (force: boolean) => {
    setScanning(true);
    setScanStage('');
    setScanContent('');
    setScanError('');

    try {
      const result = await api.scanCodebase(projectId, force);
      if (result.cached && result.summary) {
        onSummaryChange(result.summary);
        setScanning(false);
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;

      const timeout = setTimeout(() => {
        controller.abort();
        setScanError('扫描超时，请重试');
        setScanning(false);
      }, 5 * 60 * 1000);

      api.scanCodebaseStream(projectId, (event: ScanEvent) => {
        switch (event.event) {
          case 'stage':
            setScanStage(event.message || '');
            break;
          case 'chunk':
            setScanContent((prev) => prev + (event.content || ''));
            break;
          case 'done':
            clearTimeout(timeout);
            setScanContent(event.summary || '');
            setScanning(false);
            setScanStage('');
            onRefreshRef.current();
            break;
          case 'error':
            clearTimeout(timeout);
            setScanError(event.detail || '扫描失败');
            setScanning(false);
            setScanStage('');
            break;
          case 'close':
            clearTimeout(timeout);
            setScanning(false);
            break;
        }
      }, controller.signal);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : '扫描启动失败';
      if (errMsg.includes('409') || errMsg.includes('扫描进行中') || errMsg.includes('重复')) {
        setScanError('');
        subscribeToScanStream();
      } else {
        setScanError(errMsg);
        setScanning(false);
      }
    }
  }, [projectId, onSummaryChange, subscribeToScanStream]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  if (!localPath) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-[11px] font-medium text-text-tertiary">代码库概况</label>
        <button
          type="button"
          disabled={scanning || dirty}
          onClick={() => startScan(!!(codebaseSummary || initialScanStatus === 'completed'))}
          className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-40"
        >
          {scanning ? (
            <><RefreshCw size={11} className="animate-spin" /> {scanStage || '扫描中...'}</>
          ) : codebaseSummary || initialScanStatus === 'completed' ? (
            <><RefreshCw size={11} /> 重新扫描</>
          ) : (
            <><ScanSearch size={11} /> 扫描代码库</>
          )}
        </button>
      </div>
      {dirty && !codebaseSummary && (
        <p className="text-[10px] text-amber-500">请先保存工作目录配置再扫描</p>
      )}
      {scanError && (
        <div className="flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2">
          <AlertCircle size={12} className="flex-shrink-0 text-red-500" />
          <p className="flex-1 text-[11px] text-red-500">{scanError}</p>
          <button
            onClick={() => startScan(true)}
            className="flex-shrink-0 rounded-md border border-red-500/30 px-2 py-0.5 text-[10px] font-medium text-red-500 hover:bg-red-500/10"
          >
            重试
          </button>
        </div>
      )}
      {scanning && scanContent && (
        <div className="max-h-64 overflow-y-auto rounded-md border border-accent/30 bg-bg-elevated p-3 text-xs leading-relaxed text-text-secondary">
          <pre className="whitespace-pre-wrap font-sans">{scanContent}</pre>
          <span className="inline-block h-3 w-1.5 animate-pulse bg-accent/60" />
        </div>
      )}
      {!scanning && (codebaseSummary || scanContent) ? (
        <div className="max-h-64 overflow-y-auto rounded-md border border-border bg-bg-elevated p-3 text-xs leading-relaxed text-text-secondary prose-headings:text-text-primary prose-headings:font-semibold">
          <pre className="whitespace-pre-wrap font-sans">{codebaseSummary || scanContent}</pre>
        </div>
      ) : !scanning && !scanError && initialScanStatus === 'completed' ? (
        <div className="flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-3 py-2">
          <RefreshCw size={11} className="animate-spin text-text-muted" />
          <p className="text-[10px] text-text-muted">加载扫描结果...</p>
        </div>
      ) : !scanning && !scanError && (
        <p className="text-[10px] text-text-muted">尚未扫描。点击扫描后，AI 将分析代码库结构并生成总结，供后续 Agent 交互使用。</p>
      )}
      {/* T4: 扫描增量 diff 展示 */}
      {lastScanDiff && lastScanDiff.type === 'incremental' && (
        <ScanDiffBadge diff={lastScanDiff} />
      )}
    </div>
  );
}

function ScanDiffBadge({ diff }: { diff: ScanDiff }) {
  const items: string[] = [];
  if (Array.isArray(diff.aggregates_added) && diff.aggregates_added.length > 0) {
    items.push(`+${diff.aggregates_added.length} 聚合 (${diff.aggregates_added.join(', ')})`);
  }
  if (Array.isArray(diff.aggregates_removed) && diff.aggregates_removed.length > 0) {
    items.push(`-${diff.aggregates_removed.length} 聚合 (${diff.aggregates_removed.join(', ')})`);
  }
  if (Array.isArray(diff.subdomains_added) && diff.subdomains_added.length > 0) {
    items.push(`+${diff.subdomains_added.length} 子域`);
  }
  if (!items.length) return null;

  return (
    <div className="flex items-center gap-2 rounded-md border border-accent/20 bg-accent/5 px-3 py-1.5">
      <GitCompare size={11} className="text-accent" />
      <p className="text-[10px] text-text-secondary">
        <span className="font-medium text-accent">上次变更:</span>{' '}
        {items.join(' · ')}
      </p>
    </div>
  );
}
