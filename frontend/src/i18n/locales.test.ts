import { describe, expect, it } from 'vitest'

import en from './locales/en.json'
import es from './locales/es.json'
import itLocale from './locales/it.json'

function flatten(value: unknown, prefix = ''): Map<string, string> {
  const out = new Map<string, string>()
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      for (const [k, v] of flatten(child, prefix ? `${prefix}.${key}` : key)) out.set(k, v)
    }
  } else {
    out.set(prefix, String(value))
  }
  return out
}

const placeholders = (text: string) => [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort()

const reference = flatten(itLocale)

describe.each([
  ['en', en],
  ['es', es],
])('locale %s', (_, locale) => {
  const flat = flatten(locale)

  it('has exactly the same keys as Italian', () => {
    expect([...flat.keys()].sort()).toEqual([...reference.keys()].sort())
  })

  it('has no empty strings and keeps the same placeholders', () => {
    for (const [key, text] of reference) {
      const translated = flat.get(key) ?? ''
      expect(translated.trim(), key).not.toBe('')
      expect(placeholders(translated), key).toEqual(placeholders(text))
    }
  })
})
