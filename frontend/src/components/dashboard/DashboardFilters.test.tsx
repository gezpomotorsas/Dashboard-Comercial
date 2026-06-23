import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DashboardFilters } from '@/components/dashboard/DashboardFilters'
import type { DashboardFiltersResponse } from '@/types/dashboard'

const filters: DashboardFiltersResponse = {
  weeks: [
    { value: '2026-06-15', label: '15 Jun – 21 Jun' },
    { value: '2026-06-08', label: '08 Jun – 14 Jun' },
  ],
  brands: [
    { value: 'all', label: 'Todas las marcas' },
    { value: 'voyah', label: 'Voyah' },
  ],
  owners: [
    { value: 'all', label: 'Todos los asesores' },
    { value: '1', label: 'Ana López' },
  ],
  pipelines: [{ value: 'all', label: 'Todos los pipelines' }],
  metadata: { activity_window_days: 60 },
}

describe('DashboardFilters', () => {
  it('changes week', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <DashboardFilters
        filters={filters}
        values={{
          week_start: '2026-06-15',
          brand: 'all',
          owner_id: 'all',
          pipeline_id: 'all',
        }}
        onChange={onChange}
      />,
    )

    await user.selectOptions(screen.getAllByLabelText('Semana')[0], '2026-06-08')
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ week_start: '2026-06-08' }))
  })

  it('changes brand', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <DashboardFilters
        filters={filters}
        values={{
          week_start: '2026-06-15',
          brand: 'all',
          owner_id: 'all',
          pipeline_id: 'all',
        }}
        onChange={onChange}
      />,
    )

    await user.selectOptions(screen.getAllByLabelText('Marca')[0], 'voyah')
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ brand: 'voyah' }))
  })
})
