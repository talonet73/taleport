import { Navigate, Route, Routes } from 'react-router'

import { GeneratorPage } from '../pages/generator/GeneratorPage'
import { LongContentPage } from '../pages/longContent/LongContentPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { SettingsPage } from '../pages/settings/SettingsPage'
import { ThemeDetailPage } from '../pages/themes/ThemeDetailPage'
import { TodayPage } from '../pages/today/TodayPage'
import { TopicEditor } from '../pages/topics/TopicEditor'
import { TopicsPage } from '../pages/topics/TopicsPage'
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
        <Route path="/generator" element={<GeneratorPage />} />
        <Route path="/long-content" element={<LongContentPage />} />
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
