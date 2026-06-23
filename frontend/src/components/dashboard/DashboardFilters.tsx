import { Filter, X } from 'lucide-react'
import { useState } from 'react'
import type { DashboardFiltersResponse } from '@/types/dashboard'
import { Label, Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface DashboardFilterValues {
  week_start: string
  brand: string
  owner_id: string
  pipeline_id: string
}

interface DashboardFiltersProps {
  filters: DashboardFiltersResponse
  values: DashboardFilterValues
  onChange: (values: DashboardFilterValues) => void
}

function FilterFields({
  filters,
  values,
  onChange,
}: DashboardFiltersProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <Label htmlFor="week">Semana</Label>
        <Select
          id="week"
          value={values.week_start}
          onChange={(e) => onChange({ ...values, week_start: e.target.value })}
        >
          {filters.weeks.map((w) => (
            <option key={w.value} value={w.value}>
              {w.label}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="brand">Marca</Label>
        <Select
          id="brand"
          value={values.brand}
          onChange={(e) => onChange({ ...values, brand: e.target.value })}
        >
          {filters.brands.map((b) => (
            <option key={b.value} value={b.value}>
              {b.label}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="owner">Asesor</Label>
        <Select
          id="owner"
          value={values.owner_id}
          onChange={(e) => onChange({ ...values, owner_id: e.target.value })}
        >
          {filters.owners.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="pipeline">Pipeline</Label>
        <Select
          id="pipeline"
          value={values.pipeline_id}
          onChange={(e) => onChange({ ...values, pipeline_id: e.target.value })}
        >
          {filters.pipelines.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </Select>
      </div>
    </div>
  )
}

export function DashboardFilters({ filters, values, onChange }: DashboardFiltersProps) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="rounded-[14px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between lg:hidden">
        <div className="flex items-center gap-2 font-medium text-slate-800">
          <Filter className="h-4 w-4" />
          Filtros
        </div>
        <Button variant="outline" onClick={() => setMobileOpen((o) => !o)}>
          {mobileOpen ? <X className="h-4 w-4" /> : <Filter className="h-4 w-4" />}
        </Button>
      </div>
      <div className={cn('hidden lg:block')}>
        <FilterFields filters={filters} values={values} onChange={onChange} />
      </div>
      {mobileOpen && (
        <div className="lg:hidden">
          <FilterFields filters={filters} values={values} onChange={onChange} />
        </div>
      )}
    </div>
  )
}
