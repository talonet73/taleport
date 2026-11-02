import type { ReactNode } from 'react'

interface CardProps {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
}

export function Card({ title, description, actions, children, className = '' }: CardProps) {
  return (
    <section
      className={`rounded-card border border-line bg-surface p-6 shadow-card ${className}`}
    >
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-1 max-w-prose text-muted">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}
