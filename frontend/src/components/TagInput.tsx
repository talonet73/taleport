import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

interface TagInputProps {
  values: string[]
  onChange: (values: string[]) => void
  placeholder: string
  label: string
  prefix?: string
}

/** Chips editor: Enter or comma adds, Backspace on an empty field removes the last chip. */
export function TagInput({ values, onChange, placeholder, label, prefix = '' }: TagInputProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState('')

  const add = (raw: string) => {
    const parts = raw
      .split(',')
      // With a visual prefix (e.g. "#") the stored value never repeats it.
      .map((p) => (prefix ? p.trim().replace(/^#+/, '') : p.trim()))
      .filter(Boolean)
    const known = new Set(values.map((v) => v.toLowerCase()))
    const next = [...values]
    for (const part of parts) {
      if (!known.has(part.toLowerCase())) {
        known.add(part.toLowerCase())
        next.push(part)
      }
    }
    onChange(next)
    setDraft('')
  }

  return (
    <div className="flex min-h-11 flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-raised px-2 py-1.5 focus-within:border-accent">
      {values.map((value) => (
        <span
          key={value}
          className="flex items-center gap-1 rounded-full bg-surface px-3 py-1 text-ink ring-1 ring-line"
        >
          {prefix}
          {value}
          <button
            type="button"
            onClick={() => onChange(values.filter((v) => v !== value))}
            aria-label={t('common.removeItem', { item: value })}
            className="rounded-full text-muted hover:text-ink"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </span>
      ))}
      <input
        value={draft}
        aria-label={label}
        placeholder={values.length ? '' : placeholder}
        onChange={(e) => {
          if (e.target.value.endsWith(',')) add(e.target.value)
          else setDraft(e.target.value)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            if (draft.trim()) add(draft)
          } else if (e.key === 'Backspace' && !draft && values.length) {
            onChange(values.slice(0, -1))
          }
        }}
        onBlur={() => draft.trim() && add(draft)}
        className="min-w-40 flex-1 bg-transparent px-1 py-1 text-ink outline-none placeholder:text-muted"
      />
    </div>
  )
}
