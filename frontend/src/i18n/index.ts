import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import type { Language } from '../api/types'
import en from './locales/en.json'
import es from './locales/es.json'
import it from './locales/it.json'

export const resources = { it: { translation: it }, en: { translation: en }, es: { translation: es } }

void i18n.use(initReactI18next).init({
  resources,
  lng: 'it',
  fallbackLng: 'it',
  interpolation: { escapeValue: false },
})

export function setLanguage(language: Language): void {
  if (i18n.language !== language) void i18n.changeLanguage(language)
  document.documentElement.lang = language
}

export default i18n
