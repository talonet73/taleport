import i18n from '../../i18n'

/** "Italiano · Italia" in the current UI language, built from the edition code (e.g. "it-IT"). */
export function editionLabel(code: string, uiLanguage: string): string {
  const [language, country] = code.split('-')
  return `${i18n.t(`languages.${language}`)} · ${countryName(country, uiLanguage)}`
}

export function countryName(country: string, uiLanguage: string): string {
  try {
    return new Intl.DisplayNames([uiLanguage], { type: 'region' }).of(country) ?? country
  } catch {
    return country
  }
}
