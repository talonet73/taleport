import {
  Archive,
  CalendarDays,
  CalendarRange,
  FileDown,
  FileText,
  type LucideIcon,
  PenLine,
  Settings,
  Sun,
  Tags,
  TrendingUp,
} from 'lucide-react'

export interface NavItem {
  path: string
  labelKey: string
  icon: LucideIcon
  /** Development phase that delivers the page; undefined when it already exists. */
  phase?: number
}

export const NAV_ITEMS: NavItem[] = [
  { path: '/today', labelKey: 'nav.today', icon: Sun },
  { path: '/week', labelKey: 'nav.week', icon: CalendarRange },
  { path: '/trends', labelKey: 'nav.trends', icon: TrendingUp },
  { path: '/generator', labelKey: 'nav.generator', icon: PenLine },
  { path: '/long-content', labelKey: 'nav.longContent', icon: FileText },
  { path: '/calendar', labelKey: 'nav.calendar', icon: CalendarDays },
  { path: '/topics', labelKey: 'nav.topics', icon: Tags },
  { path: '/archive', labelKey: 'nav.archive', icon: Archive },
  { path: '/reports', labelKey: 'nav.reports', icon: FileDown, phase: 8 },
  { path: '/settings', labelKey: 'nav.settings', icon: Settings },
]
