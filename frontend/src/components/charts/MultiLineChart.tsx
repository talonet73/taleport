import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { echarts, longDay, SERIES_TOKENS, shortDay, token, useThemeVersion } from './echartsSetup'

interface Series {
  name: string
  values: number[]
}

/**
 * Daily lines, up to 5 series in the validated fixed order. One axis; legend for >= 2
 * series with the names written out (identity never by color alone); crosshair tooltip
 * listing every series by name; table view toggle.
 */
export function MultiLineChart({ days, series, title }: { days: string[]; series: Series[]; title: string }) {
  const { t, i18n } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)
  const themeVersion = useThemeVersion()
  const [showTable, setShowTable] = useState(false)
  const shown = series.slice(0, SERIES_TOKENS.length)

  useEffect(() => {
    if (!ref.current || showTable || !shown.length) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'svg' })
    const ink = token('--tp-text')
    const muted = token('--tp-muted')
    const grid = token('--tp-chart-grid')
    const surface = token('--tp-surface-raised')
    const colors = SERIES_TOKENS.map(token)
    chart.setOption({
      animationDuration: 300,
      color: colors,
      grid: { left: 36, right: 16, top: shown.length > 1 ? 36 : 16, bottom: 28 },
      legend:
        shown.length > 1
          ? { top: 0, left: 0, textStyle: { color: ink }, icon: 'roundRect', itemWidth: 14, itemHeight: 4 }
          : undefined,
      xAxis: {
        type: 'category',
        data: days.map((d) => shortDay(d, i18n.language)),
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
        formatter: (params: { dataIndex: number; seriesName: string; value: number; marker: string }[]) =>
          `${longDay(days[params[0].dataIndex], i18n.language)}<br/>` +
          params.map((p) => `${p.marker} ${p.seriesName}: <b>${p.value}</b>`).join('<br/>'),
      },
      series: shown.map((s) => ({
        name: s.name,
        type: 'line',
        data: s.values,
        smooth: 0.2,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 2 },
        itemStyle: { borderColor: surface, borderWidth: 2 },
        // No end labels: with close values they pile up unreadably. Identity comes from the
        // legend, the tooltip and the table view; hovering a legend entry highlights its line.
        emphasis: { focus: 'series' },
      })),
    })
    const resize = () => chart.resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.dispose()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, series, themeVersion, i18n.language, showTable])

  if (!shown.length) return <p className="text-muted">{t('trends.noData')}</p>

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
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className="text-left text-muted">
                <th className="py-1 pr-2 font-medium">{t('themes.day')}</th>
                {shown.map((s) => (
                  <th key={s.name} className="py-1 pr-2 text-right font-medium">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {days.map((d, i) => (
                <tr key={d} className="border-t border-line text-ink">
                  <td className="py-1.5 pr-2">{longDay(d, i18n.language)}</td>
                  {shown.map((s) => (
                    <td key={s.name} className="py-1.5 pr-2 text-right">
                      {s.values[i]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={ref} role="img" aria-label={title} className="h-72 w-full" />
      )}
    </div>
  )
}
