import { X } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

/** Accessible dialog: Escape closes, focus moves inside, backdrop click closes. */
export function Modal({ title, onClose, children, wide }: ModalProps) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.querySelector<HTMLElement>('textarea, input, select, button')?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-40 grid place-items-center bg-black/50 p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`max-h-[90vh] w-full overflow-y-auto rounded-card border border-line bg-surface p-6 shadow-card ${
          wide ? 'max-w-3xl' : 'max-w-xl'
        }`}
      >
        <header className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-xl font-semibold text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="rounded-full p-1.5 text-muted hover:bg-surface-raised hover:text-ink"
          >
            <X className="size-5" aria-hidden />
          </button>
        </header>
        {children}
      </div>
    </div>
  )
}
