import { useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import React, { useCallback, useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Option } from 'effect'
import { Loader2Icon } from 'lucide-react'
import { FlashcardContent } from './flashcard-content'
import type { FlashcardDto } from '@/integrations/api/client'
import { flashcardDetailRoute } from '@/routes/_config'
import { refreshFlashcardsAtom } from '@/data-acess/flashcard'
import { useGeneratedResourceSnapshot } from '@/hooks/use-generated-resource-snapshot'
import {
  flashcardDetailStateAtom,
  gotItRightAtom,
  gotItWrongAtom,
  initializeQueueAtom,
  resetAtom,
  resetWrongAtom,
  setShowAnswerAtom,
  submitPendingPracticeRecordsAtom,
} from '@/features/flashcard/state/flashcard-detail-state'

type Props = React.ComponentProps<'div'> & {
  flashcardGroupId: string
}

export const FlashcardDetail = ({ flashcardGroupId, ...props }: Props) => {
  const { projectId } = flashcardDetailRoute.useParams()

  const navigate = useNavigate()

  const stateResult = useAtomValue(flashcardDetailStateAtom(flashcardGroupId))

  const reset = useAtomSet(resetAtom)
  const initializeQueue = useAtomSet(initializeQueueAtom, { mode: 'promise' })
  const refreshFlashcards = useAtomSet(refreshFlashcardsAtom, {
    mode: 'promise',
  })
  const resetWrong = useAtomSet(resetWrongAtom)
  const submitPendingPracticeRecords = useAtomSet(
    submitPendingPracticeRecordsAtom,
    {
      mode: 'promise',
    },
  )
  const setShowAnswer = useAtomSet(setShowAnswerAtom)
  const gotItRight = useAtomSet(gotItRightAtom)
  const gotItWrong = useAtomSet(gotItWrongAtom)
  const snapshot = useGeneratedResourceSnapshot<Array<FlashcardDto>>({
    projectId,
    targetType: 'flashcards',
    targetId: flashcardGroupId,
    dataPath: `/api/v1/projects/${projectId}/flashcard-groups/${flashcardGroupId}/flashcards`,
  })

  const handleClose = useCallback(() => {
    navigate({
      to: '/dashboard/p/$projectId',
      params: { projectId },
    })
  }, [navigate, projectId])

  const handleSubmitPendingPracticeRecords = async () => {
    await submitPendingPracticeRecords({ flashcardGroupId, projectId })
    handleClose()
  }

  const handleRetry = () => {
    reset({ flashcardGroupId })
    initializeQueue({ projectId, flashcardGroupId, includeMastered: false })
  }

  const handleRetryWrong = (wrongIds: Array<string>) => {
    resetWrong({
      flashcardGroupId,
      wrongCardIds: new Set(wrongIds),
    })
  }

  // Keyboard shortcuts: Spacebar for toggle answer, R for "Got it", W for "Not yet"
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if user is typing in an input/textarea
      const target = event.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return
      }

      // Get current state
      if (Option.isNone(stateResult)) return
      const currentState = stateResult.value
      if (!currentState.currentCardId) return

      // Spacebar toggles show/hide answer
      if (event.code === 'Space' || event.key === ' ') {
        event.preventDefault()
        setShowAnswer({ flashcardGroupId, show: !currentState.showAnswer })
        return
      }

      if (event.key === 'r' || event.key === 'R') {
        event.preventDefault()
        gotItRight({ flashcardGroupId, projectId })
      } else if (event.key === 'w' || event.key === 'W') {
        event.preventDefault()
        gotItWrong({ flashcardGroupId, projectId })
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    projectId,
    stateResult,
    flashcardGroupId,
    setShowAnswer,
    gotItRight,
    gotItWrong,
  ])

  // Initialize queue when component mounts or group changes
  // Wait a bit to ensure flashcards are loaded first
  useEffect(() => {
    if (snapshot.checking || snapshot.isGenerating) return
    reset({ flashcardGroupId })
    const timer = window.setTimeout(() => {
      void refreshFlashcards({ projectId, flashcardGroupId }).then(() =>
        initializeQueue({
          projectId,
          flashcardGroupId,
          includeMastered: false,
        }),
      )
    }, 100)
    return () => window.clearTimeout(timer)
  }, [
    flashcardGroupId,
    initializeQueue,
    projectId,
    refreshFlashcards,
    reset,
    snapshot.checking,
    snapshot.isGenerating,
  ])

  if (!projectId) return null

  const flashcards = snapshot.data ?? []
  const queueIsReady = Option.isSome(stateResult) && stateResult.value.isReady
  const showIncrementalGeneration =
    snapshot.checking ||
    snapshot.isGenerating ||
    (snapshot.isManaged && !queueIsReady && flashcards.length > 0)

  if (showIncrementalGeneration) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2Icon className="size-4 animate-spin" />
          <span>
            {flashcards.length > 0
              ? snapshot.isGenerating
                ? `已生成 ${flashcards.length} 张闪卡，后续内容正在生成…`
                : `已生成 ${flashcards.length} 张闪卡，正在准备复习…`
              : snapshot.checking
                ? '正在加载闪卡…'
                : '正在生成第一张闪卡…'}
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {flashcards.map((card, index) => (
            <div key={card.id} className="rounded-xl border bg-background p-4">
              <div className="text-xs text-muted-foreground">
                闪卡 {index + 1}
              </div>
              <div className="mt-2 font-medium">{card.question}</div>
              <div className="mt-3 text-sm text-muted-foreground">
                {card.answer}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 min-h-0" {...props}>
      <FlashcardContent
        flashcardGroupId={flashcardGroupId}
        projectId={projectId}
        onSubmit={handleSubmitPendingPracticeRecords}
        onRetry={handleRetry}
        onRetryWrong={handleRetryWrong}
        onClose={handleClose}
      />
    </div>
  )
}
