import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from './KpiCard'
import type { DashboardKpiCard } from '../../types/dashboard'

function makeCard(overrides: Partial<DashboardKpiCard> = {}): DashboardKpiCard {
  return {
    code: 'leads_created',
    label: 'Leads creados',
    value: 12,
    unit: 'count',
    previous_value: 10,
    change_value: 2,
    change_percentage: 20,
    direction: 'higher_is_better',
    data_status: 'available',
    status_reason: null,
    display_value: null,
    ...overrides,
  }
}

describe('KpiCard', () => {
  it('muestra el valor disponible con tendencia positiva', () => {
    render(<KpiCard card={makeCard()} />)

    expect(screen.getByText('Leads creados')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('+20%')).toBeInTheDocument()
    expect(screen.getByText('vs. sem. anterior')).toBeInTheDocument()
  })

  it('muestra Sin datos cuando el KPI no está disponible', () => {
    render(
      <KpiCard
        card={makeCard({
          code: 'close_rate',
          label: 'Tasa de cierre',
          value: 0,
          display_value: null,
          data_status: 'unavailable',
          change_value: null,
          change_percentage: null,
          previous_value: null,
        })}
      />,
    )

    expect(screen.getByText('Sin datos')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('usa display_value del backend para montos COP', () => {
    render(
      <KpiCard
        card={makeCard({
          code: 'pipeline_created_amount',
          label: 'Pipeline generado',
          value: 24_500_000,
          unit: 'cop',
          display_value: '$24,5 M',
          change_percentage: null,
          change_value: null,
          previous_value: null,
        })}
      />,
    )

    expect(screen.getByText('$24,5 M')).toBeInTheDocument()
  })

  it('muestra cambio para lower_is_better cuando sube el valor', () => {
    render(
      <KpiCard
        card={makeCard({
          code: 'critical_quality_issues',
          label: 'Hallazgos críticos',
          value: 5,
          previous_value: 3,
          change_value: 2,
          change_percentage: 66.7,
          direction: 'lower_is_better',
          unit: 'count',
        })}
      />,
    )

    expect(screen.getByText('+66.7%')).toBeInTheDocument()
  })
})
