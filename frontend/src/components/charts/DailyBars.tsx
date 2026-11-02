import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { echarts, longDay, shortDay, token, useThemeVersion } from './echartsSetup'

/** Single-series daily columns (magnitude, one hue) with per-bar tooltip and table view. */
export function DailyBars({ days, values, title, unit }: { days: string[]; values: number[]; title: string; unit: (n: number) => string }) {
  const { t, i18n } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)
  const themeVersion = useThemeVersion()
  const [showTable, setShowTable] = useState(false)

  useEffect(() => {
    if (!ref.current || showTable) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'svg' })
    const grid = token('--tp-chart-grid')
    const muted = token('--tp-muted')
    const ink = token('--tp-text')
    chart.setOption({
      animationDuration: 300,
      grid: { left: 36, right: 12, top: 16, bottom: 28 },
      xAxis: {
        type: 'category',
        data: days.map((d) => shortDay(d, i18n.language)),
        axisLine: { lineStyle: { color: grid } },
        axisTick: { show: false },
        axisLabel: { color: muted, fontSize: 12 },
      },
      yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: grid } }, axisLabel: { color: muted } },
      tooltip: {
        trigger: 'item',
        backgroundColor: token('--tp-surface-raised'),
        borderColor: grid,
        textStyle: { color: ink },
        formatter: (p: { dataIndex: number; value: number }) => `${longDay(days[p.dataIndex], i18n.language)}<br/><b>${unit(p.value)}</b>`,
      },
      series: [
        {
          type: 'bar',
          data: values,
          barMaxWidth: 36,
          itemStyle: { color: token('--tp-chart-1'), borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: 'top', color: ink, fontSize: 12 },
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
  }, [days, values, themeVersion, i18n.language, showTable])

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
          <caption className="sr-only">{title}</caption>
          <tbody>
            {days.map((d, i) => (
              <tr key={d} className="border-t border-line text-ink">
                <td className="py-1.5">{longDay(d, i18n.language)}</td>
                <td className="py-1.5 text-right font-medium">{values[i]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div ref={ref} role="img" aria-label={title} className="h-56 w-full" />
      )}
    </div>
  )
}
