export function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-border/50 ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <SkeletonLine className="mb-3 h-4 w-2/3" />
      <SkeletonLine className="mb-2 h-3 w-full" />
      <SkeletonLine className="h-3 w-1/2" />
    </div>
  );
}

export function SkeletonListItem() {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <SkeletonLine className="h-1.5 w-1.5 rounded-full" />
      <SkeletonLine className="h-3 flex-1" />
      <SkeletonLine className="h-4 w-12 rounded-full" />
    </div>
  );
}

export function ProjectListSkeleton() {
  return (
    <div className="grid auto-rows-fr grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function ExperienceListSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-bg-card p-4">
          <div className="mb-2 flex items-center gap-2">
            <SkeletonLine className="h-1.5 w-1.5 rounded-full" />
            <SkeletonLine className="h-4 w-1/2" />
            <SkeletonLine className="h-3 w-10 rounded-full" />
          </div>
          <SkeletonLine className="mb-2 h-3 w-full" />
          <SkeletonLine className="mb-3 h-3 w-3/4" />
          <div className="flex gap-2">
            <SkeletonLine className="h-4 w-10 rounded" />
            <SkeletonLine className="h-4 w-14 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TodoDetailSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <SkeletonLine className="h-4 w-4 rounded" />
        <SkeletonLine className="h-4 w-48" />
      </div>
      <div className="flex flex-1">
        <div className="w-[140px] border-r border-border p-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <SkeletonLine key={i} className="mb-2 h-6 w-full rounded-md" />
          ))}
        </div>
        <div className="flex-1 p-6">
          <SkeletonLine className="mb-4 h-5 w-40" />
          <SkeletonLine className="mb-3 h-4 w-full" />
          <SkeletonLine className="mb-3 h-4 w-3/4" />
          <SkeletonLine className="h-32 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}

export function VersionListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-bg-card p-4">
          <div className="mb-3 flex items-center gap-3">
            <SkeletonLine className="h-3 w-3" />
            <SkeletonLine className="h-4 w-32" />
            <SkeletonLine className="h-4 w-14 rounded-full" />
          </div>
          <SkeletonLine className="mb-2 h-1.5 w-full rounded-full" />
          <div className="space-y-1">
            {Array.from({ length: 3 }).map((_, j) => (
              <SkeletonListItem key={j} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
