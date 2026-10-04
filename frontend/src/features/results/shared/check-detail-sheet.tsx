import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { CheckDetail, type ExplanationState } from '@/components/results'
import {
  Button,
  Kbd,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Tooltip,
} from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { useExplainCheck, useHealth } from '@/lib/queries'
import type { CheckResult, ExplainMode, ExplainProvider, Location } from '@/lib/types'
import { AiExplain } from './ai-explain'

interface CheckDetailSheetProps {
  analysisId: string
  check: CheckResult | null
  checksById: ReadonlyMap<string, CheckResult>
  navList: string[]
  onNavigate: (checkId: string) => void
  onClose: () => void
  onOpenFile: (location: Location) => void
}

/** Right-side detail panel (full screen on mobile) for one check, with explanations on demand. */
export function CheckDetailSheet({
  analysisId,
  check,
  checksById,
  navList,
  onNavigate,
  onClose,
  onOpenFile,
}: CheckDetailSheetProps) {
  const index = check ? navList.indexOf(check.id) : -1
  const prevId = index > 0 ? navList[index - 1] : undefined
  const nextId = index >= 0 && index < navList.length - 1 ? navList[index + 1] : undefined

  return (
    <Sheet open={check !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent widthClassName="sm:max-w-2xl">
        {check && (
          <>
            <SheetHeader className="flex items-center gap-2 py-3">
              <SheetTitle className="sr-only">Check detail</SheetTitle>
              <SheetDescription className="min-w-0 flex-1 truncate font-mono text-2xs text-fg-subtle">{check.id}</SheetDescription>
              {navList.length > 1 && index >= 0 && (
                <div className="flex shrink-0 items-center gap-1">
                  <span className="mr-1 text-2xs text-fg-subtle tabular">
                    {index + 1} / {navList.length}
                  </span>
                  <Tooltip content={<span className="inline-flex items-center gap-1.5">Previous <Kbd>K</Kbd></span>}>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label="Previous check"
                      disabled={!prevId}
                      onClick={() => prevId && onNavigate(prevId)}
                    >
                      <ChevronUp aria-hidden />
                    </Button>
                  </Tooltip>
                  <Tooltip content={<span className="inline-flex items-center gap-1.5">Next <Kbd>J</Kbd></span>}>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label="Next check"
                      disabled={!nextId}
                      onClick={() => nextId && onNavigate(nextId)}
                    >
                      <ChevronDown aria-hidden />
                    </Button>
                  </Tooltip>
                </div>
              )}
            </SheetHeader>
            <SheetBody className="px-5 py-5">
              {/* key: explanation state and AI consent never leak from one check to another */}
              <CheckDetailBody
                key={check.id}
                analysisId={analysisId}
                check={check}
                checksById={checksById}
                onNavigate={onNavigate}
                onOpenFile={onOpenFile}
              />
            </SheetBody>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function CheckDetailBody({
  analysisId,
  check,
  checksById,
  onNavigate,
  onOpenFile,
}: {
  analysisId: string
  check: CheckResult
  checksById: ReadonlyMap<string, CheckResult>
  onNavigate: (checkId: string) => void
  onOpenFile: (location: Location) => void
}) {
  const explain = useExplainCheck(analysisId)
  const health = useHealth()
  const [explanation, setExplanation] = useState<ExplanationState | null>(null)
  const [lastProvider, setLastProvider] = useState<ExplainProvider>('template')

  const request = (mode: ExplainMode, provider: ExplainProvider) => {
    setLastProvider(provider)
    setExplanation({ mode, status: 'loading' })
    explain.mutate(
      { checkId: check.id, mode, provider },
      {
        onSuccess: (data) => setExplanation({ mode, status: 'success', data }),
        onError: (error) => setExplanation({ mode, status: 'error', error: errorMessage(error) }),
      },
    )
  }

  const blocked = check.blocked_by ? checksById.get(check.blocked_by) : undefined
  const aiEnabled = health.data?.ai.enabled === true

  return (
    <div className="space-y-5">
      <CheckDetail
        check={check}
        onOpenSource={onOpenFile}
        onExplain={(mode) => request(mode, 'template')}
        explanation={explanation}
        onSelectCheck={blocked ? onNavigate : undefined}
        blockedByTitle={blocked?.title}
      />
      {aiEnabled && (
        <AiExplain
          analysisId={analysisId}
          check={check}
          busy={explanation?.status === 'loading' && lastProvider === 'ai'}
          onSend={(mode) => request(mode, 'ai')}
        />
      )}
    </div>
  )
}
