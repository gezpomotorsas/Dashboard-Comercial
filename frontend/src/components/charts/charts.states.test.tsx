import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LeadsDealsTrendChart } from '@/components/charts/LeadsDealsTrendChart'
import { BrandResultsChart } from '@/components/charts/BrandResultsChart'

describe('Dashboard states', () => {
  it('empty state message', () => {
    render(<EmptyState message="Sin datos" />)
    expect(screen.getByText('Sin datos')).toBeInTheDocument()
  })

  it('error state with retry', () => {
    render(<ErrorState message="API no disponible" onRetry={() => undefined} />)
    expect(screen.getByText('API no disponible')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument()
  })
})

describe('Charts empty data', () => {
  it('leads deals trend empty', () => {
    render(
      <LeadsDealsTrendChart
        data={[{ week_start: '2026-06-15', week_label: 'Jun', leads_created: 0, deals_created: 0 }]}
      />,
    )
    expect(screen.getByText(/sin resultados/i)).toBeInTheDocument()
  })

  it('brand results includes unknown', () => {
    render(
      <BrandResultsChart
        data={[
          {
            brand: 'unknown',
            brand_label: 'Unknown',
            leads_created: null,
            leads_data_status: 'unavailable',
            deals_created: 2,
            won_deals: 0,
          },
        ]}
      />,
    )
    expect(screen.getByText('Resultados por marca')).toBeInTheDocument()
    expect(screen.getByText('Leads, negocios creados y ganados')).toBeInTheDocument()
  })
})
