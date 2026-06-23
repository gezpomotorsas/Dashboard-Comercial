export function mergeWeeklyCounts(
  primary: Array<{ week_start: string }>,
  secondary: Array<{ week_start: string }> | undefined,
  primaryKey: string,
  secondaryKey: string,
  primaryLabel: string,
  secondaryLabel: string,
): Array<Record<string, string | number>> {
  const secondaryByWeek = new Map(secondary?.map((row) => [row.week_start, row]) ?? [])
  return primary.map((row) => {
    const peer = secondaryByWeek.get(row.week_start)
    return {
      week_start: row.week_start,
      [primaryLabel]: Number((row as Record<string, unknown>)[primaryKey] ?? 0),
      [secondaryLabel]: Number((peer as Record<string, unknown> | undefined)?.[secondaryKey] ?? 0),
    }
  })
}
