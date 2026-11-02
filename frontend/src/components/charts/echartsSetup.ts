import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { useEffect, useState } from 'react'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer])

export { echarts }

export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export const SERIES_TOKENS = ['--tp-series-1', '--tp-series-2', '--tp-series-3', '--tp-series-4', '--tp-series-5']

/** Bumps when the theme changes, so charts re-read the validated colors for that theme. */
export function useThemeVersion(): number {
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const observer = new MutationObserver(() => setVersion((v) => v + 1))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return version
}

export function shortDay(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(lang, { weekday: 'short', day: 'numeric' }).format(new Date(`${iso}T12:00:00`))
}

export function longDay(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(lang, { weekday: 'long', day: 'numeric', month: 'long' }).format(
    new Date(`${iso}T12:00:00`),
  )
}
