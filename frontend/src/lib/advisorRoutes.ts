export function advisorPortfolioPath(brand: string, ownerId: string | null): string {
  return `/asesor/${encodeURIComponent(brand)}/${encodeURIComponent(ownerId ?? 'unassigned')}`
}
