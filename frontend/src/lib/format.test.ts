import { describe, expect, it } from 'vitest'
import {
  formatCopAbbrev,
  formatCopFull,
  formatCount,
  formatDurationMinutes,
  formatPercent,
  getTrendArrow,
  getTrendSentiment,
} from '@/lib/format'
import type { DashboardKpiCard } from '@/types/dashboard'

describe('formatCopAbbrev', () => {
  it('abrevia millones', () => {
    expect(formatCopAbbrev(24_500_000)).toContain('M')
  })

  it('abrevia miles', () => {
    expect(formatCopAbbrev(850_000)).toContain('mil')
  })

  it('retorna Sin datos sin valor', () => {
    expect(formatCopAbbrev(null)).toBe('Sin datos')
  })
})

describe('formatCopFull', () => {
  it('incluye sufijo COP', () => {
    expect(formatCopFull(4_280_000)).toContain('COP')
  })
})

describe('formatDurationMinutes', () => {
  it('muestra minutos', () => {
    expect(formatDurationMinutes(45)).toBe('45 min')
  })

  it('muestra horas', () => {
    expect(formatDurationMinutes(90)).toContain('h')
  })

  it('retorna Sin datos sin valor', () => {
    expect(formatDurationMinutes(null)).toBe('Sin datos')
  })
})

describe('formatPercent', () => {
  it('no muestra cero cuando no hay datos', () => {
    expect(formatPercent(null)).toBe('Sin datos')
  })
})

describe('formatCount', () => {
  it('formatea conteos', () => {
    expect(formatCount(1200)).toBe('1.200')
  })
})

describe('getTrendSentiment', () => {
  it('subida es positiva cuando higher_is_better', () => {
    expect(getTrendSentiment(5, 'higher_is_better')).toBe('positive')
  })

  it('subida es negativa cuando lower_is_better', () => {
    expect(getTrendSentiment(5, 'lower_is_better')).toBe('negative')
  })

  it('bajada es positiva cuando lower_is_better', () => {
    expect(getTrendSentiment(-10, 'lower_is_better')).toBe('positive')
  })
})

describe('getTrendArrow', () => {
  it('indica dirección del cambio', () => {
    expect(getTrendArrow(10)).toBe('up')
    expect(getTrendArrow(-2)).toBe('down')
    expect(getTrendArrow(0)).toBe('flat')
  })
})

export const sampleCard = (
  overrides: Partial<DashboardKpiCard> = {},
): DashboardKpiCard => ({
  code: 'leads_created',
  label: 'Leads creados',
  value: 10,
  unit: 'count',
  previous_value: 8,
  change_value: 2,
  change_percentage: 25,
  direction: 'higher_is_better',
  data_status: 'available',
  ...overrides,
})
