import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '@/lib/api'
import { useReanalyze } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { AnalysisReport } from '@/lib/types'

/** Starts a new analysis of the same (subject, project) pair, then opens its progress page. */
export function useReanalyzeAction(report: AnalysisReport) {
  const navigate = useNavigate()
  const { mutate, isPending } = useReanalyze()
  const run = useCallback(() => {
    if (isPending) return
    mutate(
      { subject_id: report.subject.id, project_id: report.project.id },
      {
        onSuccess: ({ job_id }) => navigate(`/jobs/${encodeURIComponent(job_id)}`),
        onError: (error) => toast({ title: 'Could not start the analysis', description: errorMessage(error), tone: 'error' }),
      },
    )
  }, [isPending, mutate, navigate, report.project.id, report.subject.id])
  return { run, isPending }
}
