import { useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { exportAllBrandsExcel, exportBrandAdvisorsExcel } from '@/lib/exportBrandAdvisorsExcel'
import type { OperatingBrand } from '@/hooks/useBrandOperating'

export function useExportBrandAdvisors(brand: OperatingBrand) {
  const queryClient = useQueryClient()
  const [exporting, setExporting] = useState(false)
  const [exportingAll, setExportingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exportExcel = useCallback(async () => {
    setExporting(true)
    setError(null)
    try {
      await exportBrandAdvisorsExcel(queryClient, brand)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No se pudo generar el Excel'
      setError(message)
      throw err
    } finally {
      setExporting(false)
    }
  }, [queryClient, brand])

  const exportAllBrands = useCallback(async () => {
    setExportingAll(true)
    setError(null)
    try {
      await exportAllBrandsExcel(queryClient)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No se pudo generar el Excel'
      setError(message)
      throw err
    } finally {
      setExportingAll(false)
    }
  }, [queryClient])

  return { exportExcel, exportAllBrands, exporting, exportingAll, error }
}
