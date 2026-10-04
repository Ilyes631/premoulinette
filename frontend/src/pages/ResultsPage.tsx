import { Navigate, useParams } from 'react-router-dom'
import { ResultsView } from '@/features/results/results-view'
import { ResultsError, ResultsSkeleton } from '@/features/results/shared/states'
import { DEFAULT_RESULT_TAB, isResultTab, resultsPath } from '@/features/results/shared/tabs'
import { useAnalysis } from '@/lib/queries'

/** /analyses/:id and /analyses/:id/:tab — the readiness dashboard of one analysis. */
export function ResultsPage() {
  const { id, tab } = useParams()
  const analysis = useAnalysis(id)

  if (!id) return <Navigate to="/" replace />
  if (tab !== undefined && !isResultTab(tab)) return <Navigate to={resultsPath(id)} replace />
  if (analysis.isPending) return <ResultsSkeleton />
  if (analysis.isError) return <ResultsError error={analysis.error} onRetry={() => void analysis.refetch()} />

  return <ResultsView key={analysis.data.id} report={analysis.data} tab={tab ?? DEFAULT_RESULT_TAB} />
}
