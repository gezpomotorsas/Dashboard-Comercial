export function KpiCardSkeleton() {
  return (
    <div className="card animate-pulse p-5">
      <div className="mb-4 flex justify-between">
        <div className="h-4 w-28 rounded bg-slate-200" />
        <div className="h-5 w-20 rounded-full bg-slate-200" />
      </div>
      <div className="mb-3 h-9 w-32 rounded bg-slate-200" />
      <div className="h-4 w-40 rounded bg-slate-200" />
    </div>
  )
}
