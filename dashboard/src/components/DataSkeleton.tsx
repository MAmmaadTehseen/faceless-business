export function DataSkeleton() {
  return (
    <div role="status" aria-label="Loading data" className="space-y-5">
      <span className="sr-only">Loading data…</span>
      <div className="skeleton h-8 w-40" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-24" />
        ))}
      </div>
      <div className="card space-y-4">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton h-14" />
        ))}
      </div>
    </div>
  );
}
