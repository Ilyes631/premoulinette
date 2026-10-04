import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/app/AppShell'
import { ThemeProvider } from '@/components/providers/theme-provider'
import { Toaster, TooltipProvider } from '@/components/ui'
import { createQueryClient } from '@/lib/queries'
import { AnalysisProgressPage } from '@/pages/AnalysisProgressPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SpecReviewPage } from '@/pages/SpecReviewPage'

/**
 * Route map (each page lives in its own file under src/pages):
 *   /                 HomePage              import subject + project, analyze
 *   /subjects/:id     SpecReviewPage        extracted contract review & editor
 *   /jobs/:id         AnalysisProgressPage  live analysis stages
 *   /analyses/:id     ResultsPage           readiness dashboard (tabs: overview, issues, tests, files, report, history)
 *   /history          HistoryPage           all analyses
 *   /settings         SettingsPage          sandbox mode, AI, language
 */
export default function App() {
  const [queryClient] = useState(createQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<HomePage />} />
                <Route path="subjects/:id" element={<SpecReviewPage />} />
                <Route path="jobs/:id" element={<AnalysisProgressPage />} />
                <Route path="analyses/:id" element={<ResultsPage />} />
                <Route path="analyses/:id/:tab" element={<ResultsPage />} />
                <Route path="history" element={<HistoryPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
