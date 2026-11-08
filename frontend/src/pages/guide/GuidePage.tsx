import { BookOpen, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { openExternal } from '../../api/hooks'
import { Card } from '../../components/Card'

const SECTIONS = ['what', 'sources', 'daily', 'video', 'ai', 'reports', 'privacy', 'install', 'problems'] as const

/** Short user guide (IT/EN/ES), always available offline inside the app. */
export function GuidePage() {
  const { t } = useTranslation()
  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <span className="grid size-12 place-items-center rounded-2xl bg-accent-gradient text-on-accent">
          <BookOpen className="size-6" aria-hidden />
        </span>
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('guide.title')}</h1>
          <p className="text-muted">{t('guide.subtitle')}</p>
        </div>
      </div>

      <nav aria-label={t('guide.contents')} className="flex flex-wrap gap-2">
        {SECTIONS.map((id) => (
          <a key={id} href={`#guide-${id}`} className="rounded-full border border-line px-3 py-1 text-sm text-ink hover:bg-surface-raised"
            onClick={(e) => {
              e.preventDefault()
              document.getElementById(`guide-${id}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
            }}
          >
            {t(`guide.sections.${id}.title`)}
          </a>
        ))}
      </nav>

      {SECTIONS.map((id) => (
        <section key={id} id={`guide-${id}`}>
          <Card title={t(`guide.sections.${id}.title`)}>
            <ul className="max-w-prose list-disc space-y-2 pl-5 text-[15px] leading-relaxed text-ink">
              {(t(`guide.sections.${id}.items`, { returnObjects: true }) as string[]).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        </section>
      ))}

      <p className="flex flex-wrap items-center gap-3 text-sm text-muted">
        <Link to="/settings#log" className="text-accent-text hover:underline">
          {t('guide.openLog')}
        </Link>
        <button type="button" onClick={() => openExternal('https://ollama.com/download')} className="flex items-center gap-1 text-accent-text hover:underline">
          {t('guide.ollamaSite')}
          <ExternalLink className="size-3.5" aria-hidden />
        </button>
      </p>
    </div>
  )
}
