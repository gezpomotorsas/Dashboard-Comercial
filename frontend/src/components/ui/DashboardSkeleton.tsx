export function ChartSkeleton() {
  return (
    <div className="card animate-pulse p-5">
      <div className="mb-4 h-5 w-48 rounded bg-slate-200" />
      <div className="h-64 rounded-xl bg-slate-100" />
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="card animate-pulse p-5">
        <div className="mb-4 h-5 w-24 rounded bg-slate-200" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-11 rounded-xl bg-slate-100" />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="card h-36 animate-pulse p-5">
            <div className="h-4 w-28 rounded bg-slate-200" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <ChartSkeleton key={index} />
        ))}
      </div>
    </div>
  )
}
