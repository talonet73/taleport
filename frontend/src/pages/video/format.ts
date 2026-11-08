/** Number formatting for the video pages, in the interface language. */
export function makeFormat(language: string) {
  const number = new Intl.NumberFormat(language, { maximumFractionDigits: 1 })
  const compact = new Intl.NumberFormat(language, { notation: 'compact', maximumFractionDigits: 1 })
  return {
    n: (value: number | null | undefined) => (value == null ? '–' : number.format(value)),
    compact: (value: number | null | undefined) => (value == null ? '–' : compact.format(value)),
    sec: (value: number | null | undefined) => (value == null ? '–' : `${number.format(value)} s`),
    pct: (value: number | null | undefined) => (value == null ? '–' : `${number.format(value * 100)}%`),
  }
}
