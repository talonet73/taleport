/**
 * Word cloud as text: size encodes frequency (square-root scale so big words don't swamp
 * the rest); words stay in text colors and keep their count in the tooltip and for screen
 * readers. Alphabetical order keeps it stable between refreshes.
 */
export function WordCloud({ words, unit }: { words: { term: string; count: number }[]; unit: (n: number) => string }) {
  if (!words.length) return null
  const max = Math.max(...words.map((w) => w.count))
  const min = Math.min(...words.map((w) => w.count))
  const scale = (n: number) =>
    max === min ? 1 : Math.sqrt((n - min) / (max - min))
  return (
    <ul className="flex flex-wrap items-baseline justify-center gap-x-4 gap-y-1">
      {[...words]
        .sort((a, b) => a.term.localeCompare(b.term))
        .map((w) => {
          const s = scale(w.count)
          return (
            <li
              key={w.term}
              title={`${w.term}: ${unit(w.count)}`}
              style={{ fontSize: `${0.85 + s * 1.6}rem` }}
              className={`leading-tight ${s > 0.5 ? 'font-semibold text-ink' : 'text-muted'}`}
            >
              {w.term}
              <span className="sr-only">: {unit(w.count)}</span>
            </li>
          )
        })}
    </ul>
  )
}
