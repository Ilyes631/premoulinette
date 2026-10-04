import { useState } from 'react'
import { isApiError } from '@/lib/api'
import { useUpdateSpec } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { PracticalSpec } from '@/lib/types'
import { formatValidationItems, type DraftIssue } from './spec-utils'

export interface SpecSaver {
  /** Resolves true when saved. Server validation errors land in `errors`. */
  save: (spec: PracticalSpec, successTitle?: string) => Promise<boolean>
  saving: boolean
  errors: DraftIssue[]
  clearErrors: () => void
}

/** PUT /api/subjects/{id}/spec with toasts and inline 422 errors. */
export function useSpecSaver(subjectId: string): SpecSaver {
  const mutation = useUpdateSpec(subjectId)
  const [errors, setErrors] = useState<DraftIssue[]>([])

  const save = async (spec: PracticalSpec, successTitle = 'Contract saved') => {
    setErrors([])
    try {
      const view = await mutation.mutateAsync(spec)
      const blocking = view.validation.filter((i) => i.level === 'error').length
      toast({
        title: successTitle,
        description: blocking
          ? `${blocking} validation error${blocking > 1 ? 's' : ''} still need attention.`
          : 'The analysis will use this reviewed contract.',
        tone: blocking ? 'warning' : 'success',
      })
      return true
    } catch (error) {
      if (isApiError(error) && error.status === 422) {
        const items = formatValidationItems(error.validationErrors)
        setErrors(items.length ? items : [{ path: 'spec', message: error.message }])
        toast({ title: 'The contract was not saved', description: 'Fix the highlighted errors and retry.', tone: 'error' })
      } else {
        const message = error instanceof Error ? error.message : 'Unexpected error'
        setErrors([{ path: 'spec', message }])
        toast({ title: 'The contract was not saved', description: message, tone: 'error' })
      }
      return false
    }
  }

  return { save, saving: mutation.isPending, errors, clearErrors: () => setErrors([]) }
}
