import { describe, expect, it } from 'vitest'
import { ALL_OPERATING_BRANDS } from '@/lib/cascadingPrefetch'

describe('cascadingPrefetch', () => {
  it('incluye las tres marcas operativas', () => {
    expect(ALL_OPERATING_BRANDS).toEqual(['voyah', 'mhero', 'shacman'])
  })
})
