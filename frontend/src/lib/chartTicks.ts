/** Reduce etiquetas del eje X cuando hay muchas semanas en el historial. */
export function weekAxisInterval(pointCount: number): number {
  if (pointCount <= 16) return 0
  return Math.max(1, Math.floor(pointCount / 12))
}
