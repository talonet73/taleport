import { Loader2, UploadCloud } from 'lucide-react'
import { type ReactNode, useRef, useState } from 'react'

interface DropZoneProps {
  label: ReactNode
  hint?: ReactNode
  accept: string[]
  multiple?: boolean
  busy?: boolean
  progress?: number | null
  compact?: boolean
  onFiles: (files: File[]) => void
}

/** Drag files here or click to choose them. Only files with an accepted extension pass. */
export function DropZone({ label, hint, accept, multiple = true, busy, progress, compact, onFiles }: DropZoneProps) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const take = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter((f) => accept.some((ext) => f.name.toLowerCase().endsWith(ext)))
    if (files.length) onFiles(multiple ? files : files.slice(0, 1))
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        take(e.dataTransfer.files)
      }}
      className={`flex w-full flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed text-center transition ${
        compact ? 'p-4' : 'p-8'
      } ${over ? 'border-accent bg-surface-raised' : 'border-line hover:border-accent hover:bg-surface-raised'} disabled:cursor-wait`}
    >
      {busy ? (
        <Loader2 className="size-7 animate-spin text-accent-text" aria-hidden />
      ) : (
        <UploadCloud className="size-7 text-accent-text" aria-hidden />
      )}
      <span className="font-semibold text-ink">{label}</span>
      {hint && <span className="text-sm text-muted">{hint}</span>}
      {busy && progress != null && (
        <span className="h-1.5 w-48 overflow-hidden rounded-full bg-surface-raised" aria-hidden>
          <span className="block h-full bg-accent-gradient" style={{ width: `${Math.round(progress * 100)}%` }} />
        </span>
      )}
      <input
        ref={input}
        type="file"
        multiple={multiple}
        accept={accept.join(',')}
        className="hidden"
        onChange={(e) => {
          take(e.target.files)
          e.target.value = ''
        }}
      />
    </button>
  )
}
