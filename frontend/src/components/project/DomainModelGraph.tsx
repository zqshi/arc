import { useRef, useState, useEffect, useCallback } from 'react';
import type { DomainModel, DomainModelSubdomain, DomainModelRelation } from '../../types/api';
import { StrategicLayer, TacticalLayer } from './domain-model-graph-parts';

type ViewMode = 'strategic' | 'tactical' | 'all';

const SUBDOMAIN_COLORS: Record<string, { accent: string; border: string }> = {
  '核心域': { accent: '#fbbf24', border: '#fbbf24' },
  '支撑域': { accent: '#6b8cff', border: '#6b8cff' },
  '通用域': { accent: '#94a3b8', border: '#94a3b8' },
};

interface Props {
  domainModel: DomainModel;
  view: ViewMode;
}

interface NodePos {
  x: number;
  y: number;
  top: number;
  bot: number;
  left: number;
  right: number;
  w: number;
  h: number;
}

export function DomainModelGraph({ domainModel, view }: Props) {
  const boardRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [paths, setPaths] = useState<{ d: string; from: string; to: string; type: string }[]>([]);

  const activeId = selected || hovered;

  const subTypeMapBase = Object.fromEntries(
    domainModel.subdomains.map((s) => [s.name, s.type || '支撑域']),
  );

  const computePaths = useCallback(() => {
    const board = boardRef.current;
    if (!board) return;
    const br = board.getBoundingClientRect();
    const pos: Record<string, NodePos> = {};
    board.querySelectorAll<HTMLElement>('[data-node-id]').forEach((el) => {
      const r = el.getBoundingClientRect();
      pos[el.dataset.nodeId!] = {
        x: r.left - br.left + r.width / 2,
        y: r.top - br.top + r.height / 2,
        top: r.top - br.top,
        bot: r.bottom - br.top,
        left: r.left - br.left,
        right: r.right - br.left,
        w: r.width,
        h: r.height,
      };
    });

    const newPaths: typeof paths = [];

    const addPath = (fromId: string, toId: string, rel: DomainModelRelation) => {
      const f = pos[fromId];
      const t = pos[toId];
      if (!f || !t) return;
      const start = { x: f.x, y: f.y > t.y ? f.top + 8 : f.bot - 8 };
      const end = { x: t.x, y: f.y > t.y ? t.bot - 8 : t.top + 8 };
      const bend = Math.max(26, Math.abs(end.x - start.x) * 0.25);
      const my = (start.y + end.y) / 2;
      newPaths.push({
        d: `M${start.x},${start.y} C${start.x},${my - bend} ${end.x},${my + bend} ${end.x},${end.y}`,
        from: fromId,
        to: toId,
        type: rel.type,
      });
    };

    if (view === 'strategic' || view === 'all') {
      domainModel.relations.forEach((r) => addPath(`ctx_${r.from}`, `ctx_${r.to}`, r));
    }
    if (view === 'tactical' || view === 'all') {
      (domainModel.aggregate_relations || []).forEach((r) => addPath(`agg_${r.from}`, `agg_${r.to}`, r));
    }

    setPaths(newPaths);
  }, [domainModel, view]);

  useEffect(() => {
    const frame = requestAnimationFrame(computePaths);
    return () => cancelAnimationFrame(frame);
  }, [computePaths, view, selected]);

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(computePaths));
    ro.observe(board);
    return () => ro.disconnect();
  }, [computePaths]);

  const handleModuleClick = (id: string) => {
    setSelected((prev) => (prev === id ? null : id));
  };

  const getCol = (sub: string) => SUBDOMAIN_COLORS[subTypeMap[sub] || '支撑域'] || SUBDOMAIN_COLORS['支撑域'];

  // When contexts are missing, derive virtual contexts from aggregate.context field
  const effectiveContexts = domainModel.contexts.length > 0
    ? domainModel.contexts
    : (() => {
        const ctxNames = new Set(domainModel.aggregates.map((a) => a.context || '未分组'));
        return Array.from(ctxNames).map((name) => ({ name, description: '', subdomain: '' }));
      })();

  // When subdomains are missing, derive virtual subdomains from context.subdomain field
  const effectiveSubdomains = domainModel.subdomains.length > 0
    ? domainModel.subdomains
    : (() => {
        const sdNames = new Set(effectiveContexts.map((c) => c.subdomain || '通用'));
        return Array.from(sdNames).map((name) => ({
          name,
          type: (name === '通用' ? '通用域' : '支撑域') as DomainModelSubdomain['type'],
          description: '',
        }));
      })();

  const subTypeMap = {
    ...subTypeMapBase,
    ...Object.fromEntries(effectiveSubdomains.map((s) => [s.name, s.type || '支撑域'])),
  };

  const ctxBySub = effectiveSubdomains.map((sd) => ({
    info: sd,
    ctxs: effectiveContexts.filter((c) => (c.subdomain || '通用') === sd.name),
  }));

  const aggByCtx = effectiveContexts
    .map((ctx) => ({
      info: ctx,
      aggs: domainModel.aggregates.filter((a) => (a.context || '未分组') === ctx.name),
    }))
    .filter((g) => g.aggs.length > 0);

  const allRels = [...domainModel.relations, ...(domainModel.aggregate_relations || [])];

  return (
    <div className="relative" ref={boardRef}>
      {/* SVG overlay */}
      <svg
        className="pointer-events-none absolute inset-0 z-[2]"
        width="100%"
        height="100%"
        style={{ overflow: 'visible' }}
      >
        <defs>
          <marker id="dm-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L6,3 L0,6 z" fill="rgba(107,140,255,0.75)" />
          </marker>
        </defs>
        {paths.map((p, i) => {
          const isActive = activeId && (p.from === activeId || p.to === activeId);
          return (
            <path
              key={i}
              d={p.d}
              fill="none"
              stroke={isActive ? '#6b8cff' : 'rgba(107,140,255,0.6)'}
              strokeWidth={2.2}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={activeId ? (isActive ? 0.95 : 0.08) : 0.25}
              markerEnd="url(#dm-arrow)"
              style={{ transition: 'opacity 0.18s ease, stroke 0.18s ease', filter: isActive ? 'drop-shadow(0 0 6px rgba(107,140,255,0.4))' : 'none' }}
            />
          );
        })}
      </svg>

      {/* Architecture layers */}
      <div className="grid gap-3">
        {(view === 'strategic' || view === 'all') &&
          ctxBySub.map(({ info, ctxs }) => {
            const col = getCol(info.name);
            return (
              <StrategicLayer
                key={info.name}
                subdomain={info}
                contexts={ctxs}
                color={col}
                onHover={setHovered}
                onClick={handleModuleClick}
                selected={selected}
              />
            );
          })}

        {(view === 'tactical' || view === 'all') &&
          aggByCtx.map(({ info, aggs }) => (
            <TacticalLayer
              key={info.name}
              context={info}
              aggregates={aggs}
              onHover={setHovered}
              onClick={handleModuleClick}
              selected={selected}
            />
          ))}
      </div>

      {/* Relation list */}
      {allRels.length > 0 && (
        <div className="mt-4 rounded-lg border border-dashed border-border bg-bg-elevated/50 p-3">
          <h4 className="mb-2 text-xs font-semibold text-text-tertiary">集成关系清单</h4>
          <div className="space-y-1.5">
            {allRels.map((r, i) => (
              <div
                key={i}
                className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-bg-card px-3 py-2 text-[11px] transition-colors hover:border-accent/30"
                onMouseEnter={() => setHovered(`ctx_${r.from}`)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => handleModuleClick(`ctx_${r.from}`)}
              >
                <span className="font-semibold text-text-primary">{r.from}</span>
                <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">{r.type}</span>
                <span className="text-text-muted">→</span>
                <span className="font-semibold text-text-primary">{r.to}</span>
                {r.description && <span className="ml-auto text-text-muted">{r.description}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
