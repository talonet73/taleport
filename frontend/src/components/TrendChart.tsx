import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

echarts.use([LineChart, GridComponent, TooltipComponent, SVGRenderer])

interface Point {
  day: string
  count: number
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** Re-render when the theme attribute changes (dark/light are separate validated steps). */
function useThemeVersion(): number {
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const observer = new MutationObserver(() => setVersion((v) => v + 1))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return version
}

/**
 * Single-series daily count line: one validated hue (--tp-chart-1), 2px line, recessive grid,
 * crosshair tooltip. The card title names the series, so there is no legend box.
 */
export function TrendChart({ points, seriesLabel }: { points: Point[]; seriesLabel: string }) {
  const { t, i18n } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)
  const themeVersion = useThemeVersion()
  const [showTable, setShowTable] = useState(false)

  const dayLabel = (iso: string, style: 'short' | 'long') =>
    new Intl.DateTimeFormat(i18n.language, {
      weekday: style,
      day: 'numeric',
      ...(style === 'long' ? { month: 'long' } : {}),
    }).format(new Date(`${iso}T12:00:00`))

  useEffect(() => {
    if (!ref.current || showTable) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'svg' })
    const color = token('--tp-chart-1')
    const ink = token('--tp-text')
    const muted = token('--tp-muted')
    const grid = token('--tp-chart-grid')
    const surface = token('--tp-surface-raised')

    chart.setOption({
      animationDuration: 300,
      grid: { left: 36, right: 16, top: 16, bottom: 28 },
      xAxis: {
        type: 'category',
        data: points.map((p) => dayLabel(p.day, 'short')),
        boundaryGap: false,
        axisLine: { lineStyle: { color: grid } },
        axisTick: { show: false },
        axisLabel: { color: muted, fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: grid } },
        axisLabel: { color: muted, fontSize: 12 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: muted, type: 'dashed' } },
        backgroundColor: surface,
        borderColor: grid,
        textStyle: { color: ink },
        formatter: (params: { dataIndex: number }[]) => {
          const p = points[params[0].dataIndex]
          return `${dayLabel(p.day, 'long')}<br/><b>${t('themes.itemsCount', { count: p.count })}</b>`
        },
      },
      series: [
        {
          name: seriesLabel,
          type: 'line',
          data: points.map((p) => p.count),
          smooth: 0.25,
          symbol: 'circle',
          symbolSize: 8,
          showSymbol: true,
          lineStyle: { width: 2, color },
          itemStyle: { color, borderColor: surface, borderWidth: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}55` },
              { offset: 1, color: `${color}00` },
            ]),
          },
        },
      ],
    })
    const resize = () => chart.resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.dispose()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, themeVersion, i18n.language, showTable, seriesLabel])

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-full border border-line px-3 py-1 text-sm text-ink hover:bg-surface-raised"
        >
          {showTable ? t('themes.showChart') : t('themes.showTable')}
        </button>
      </div>
      {showTable ? (
        <table className="w-full text-sm">
          <caption className="sr-only">{seriesLabel}</caption>
          <thead>
            <tr className="text-left text-muted">
              <th className="py-1 font-medium">{t('themes.day')}</th>
              <th className="py-1 text-right font-medium">{t('themes.items')}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.day} className="border-t border-line text-ink">
                <td className="py-1.5">{dayLabel(p.day, 'long')}</td>
                <td className="py-1.5 text-right font-medium">{p.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div ref={ref} role="img" aria-label={seriesLabel} className="h-56 w-full" />
      )}
    </div>
  )
}
