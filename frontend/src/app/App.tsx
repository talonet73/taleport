import { Navigate, Route, Routes } from 'react-router'

import { ArchivePage } from '../pages/archive/ArchivePage'
import { AskPage } from '../pages/ask/AskPage'
import { CalendarPage } from '../pages/calendar/CalendarPage'
import { GuidePage } from '../pages/guide/GuidePage'
import { ReportsPage } from '../pages/reports/ReportsPage'
import { GeneratorPage } from '../pages/generator/GeneratorPage'
import { TrendsPage } from '../pages/trends/TrendsPage'
import { WeekPage } from '../pages/week/WeekPage'
import { LongContentPage } from '../pages/longContent/LongContentPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { SettingsPage } from '../pages/settings/SettingsPage'
import { ThemeDetailPage } from '../pages/themes/ThemeDetailPage'
import { TodayPage } from '../pages/today/TodayPage'
import { TopicEditor } from '../pages/topics/TopicEditor'
import { TopicsPage } from '../pages/topics/TopicsPage'
import { VideoProjectPage } from '../pages/video/VideoProjectPage'
import { VideoProjectsPage } from '../pages/video/VideoProjectsPage'
import { VoicesPage } from '../pages/voices/VoicesPage'
import { Layout } from './Layout'
import { NAV_ITEMS } from './navigation'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/today" replace />} />
        {NAV_ITEMS.filter((item) => item.phase).map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={<PlaceholderPage titleKey={item.labelKey} phase={item.phase!} />}
          />
        ))}
        <Route path="/today" element={<TodayPage />} />
        <Route path="/week" element={<WeekPage />} />
        <Route path="/trends" element={<TrendsPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/generator" element={<GeneratorPage />} />
        <Route path="/long-content" element={<LongContentPage />} />
        <Route path="/video" element={<VideoProjectsPage />} />
        <Route path="/voices" element={<VoicesPage />} />
        <Route path="/video/:id" element={<VideoProjectPage />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/archive" element={<ArchivePage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/guide" element={<GuidePage />} />
        <Route path="/themes/:id" element={<ThemeDetailPage />} />
        <Route path="/topics" element={<TopicsPage />} />
        <Route path="/topics/new" element={<TopicEditor />} />
        <Route path="/topics/:id" element={<TopicEditor />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Route>
    </Routes>
  )
}
