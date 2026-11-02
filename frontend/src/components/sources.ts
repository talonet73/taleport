import {
  AtSign,
  type LucideIcon,
  MessagesSquare,
  Newspaper,
  Rss,
  SquarePlay,
  TrendingUp,
} from 'lucide-react'

import type { ItemSource } from '../api/types'

// Generic icons on purpose: no third-party brand marks.
export const SOURCE_ICONS: Record<ItemSource, LucideIcon> = {
  news: Newspaper,
  rss: Rss,
  youtube: SquarePlay,
  reddit: MessagesSquare,
  trends: TrendingUp,
  x_grok: AtSign,
}
