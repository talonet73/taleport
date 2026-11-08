import { ClipboardCheck, ClipboardCopy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { copyToClipboard } from '../../api/hooks'
import { Modal } from '../../components/Modal'

/** Ready-made message asking the client for exactly what the analysis needs. */
export function ClientMessageDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const [text, setText] = useState(() => t('video.message.text'))
  const [copied, setCopied] = useState(false)

  return (
    <Modal title={t('video.message.title')} onClose={onClose} wide>
      <div className="space-y-4">
        <p className="text-muted">{t('video.message.hint')}</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={14}
          aria-label={t('video.message.title')}
          className="w-full rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent"
        />
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-full border border-line px-4 py-2 text-ink hover:bg-surface-raised">
            {t('common.close')}
          </button>
          <button
            type="button"
            onClick={() => copyToClipboard(text).then((r) => setCopied(r.copied))}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent"
          >
            {copied ? <ClipboardCheck className="size-4" aria-hidden /> : <ClipboardCopy className="size-4" aria-hidden />}
            {copied ? t('video.message.copied') : t('video.message.copy')}
          </button>
        </div>
      </div>
    </Modal>
  )
}
