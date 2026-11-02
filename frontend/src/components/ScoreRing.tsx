import { useTranslation } from 'react-i18next'

/** Hot score 0-100 as a ring meter with the number inside (single hue, value in ink). */
export function ScoreRing({ score, size = 56 }: { score: number; size?: number }) {
  const { t } = useTranslation()
  const stroke = Math.max(4, Math.round(size / 11))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const filled = (Math.max(0, Math.min(100, score)) / 100) * circumference

  return (
    <div
      role="img"
      aria-label={t('today.scoreLabel', { score })}
      className="relative shrink-0"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-surface-raised"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          className="stroke-chart-1"
        />
      </svg>
      <span
        className="absolute inset-0 grid place-items-center font-bold text-ink"
        style={{ fontSize: Math.round(size * 0.3) }}
      >
        {score}
      </span>
    </div>
  )
}
