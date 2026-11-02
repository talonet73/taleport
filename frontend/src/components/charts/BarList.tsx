/** Horizontal bars with the value and percentage written next to each: magnitude, one hue. */
export interface BarRow {
  label: string
  value: number
  share?: number // percentage, when meaningful
}

export function BarList({ rows, unit, emptyText }: { rows: BarRow[]; unit: (n: number) => string; emptyText: string }) {
  if (!rows.length) return <p className="text-muted">{emptyText}</p>
  const max = Math.max(...rows.map((r) => r.value), 1)
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.label} title={unit(row.value)}>
          <div className="mb-0.5 flex justify-between gap-3 text-sm">
            <span className="truncate text-ink">{row.label}</span>
            <span className="shrink-0 text-muted">
              {unit(row.value)}
              {row.share !== undefined && ` · ${row.share}%`}
            </span>
          </div>
          <div className="h-2 rounded-full bg-surface-raised">
            <div
              className="h-2 rounded-full bg-chart-1"
              style={{ width: `${Math.max(2, (row.value / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
