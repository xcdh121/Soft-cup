import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { Option } from 'effect'
import { FlashcardCompletionScreen } from './flashcard-completion-screen'
import { FlashcardCard } from './flashcard-card'
import { FlashcardControls } from './flashcard-controls'
import { FlashcardProgress } from './flashcard-progress'
import { Response } from '@/components/ai-elements/response'
import {
  currentFlashcardAtom,
  flashcardDetailStateAtom,
} from '@/features/flashcard/state/flashcard-detail-state'
import { flashcardProgressAtom } from '@/data-acess/flashcard'

type FlashcardContentProps = {
  flashcardGroupId: string
  projectId: string
  onSubmit: () => void
  onRetry: () => void
  onRetryWrong: (wrongIds: Array<string>) => void
  onClose: () => void
}

export const FlashcardContent = ({
  flashcardGroupId,
  projectId,
  onSubmit,
  onRetry,
  onRetryWrong,
  onClose,
}: FlashcardContentProps) => {
  const stateResult = useAtomValue(flashcardDetailStateAtom(flashcardGroupId))
  const streamProgress = useAtomValue(flashcardProgressAtom)
  const currentCard = useAtomValue(
    currentFlashcardAtom({ projectId, flashcardGroupId }),
  )

  const state = Option.isSome(stateResult) ? stateResult.value : null

  if (!state || !state.isReady) {
    if (
      streamProgress?.groupId === flashcardGroupId &&
      streamProgress.flashcards.length > 0
    ) {
      return (
        <div className="flex flex-1 flex-col gap-3 overflow-auto p-4">
          {streamProgress.flashcards.map((card, index) => (
            <div key={index} className="rounded-xl border p-4">
              <Response className="font-medium">
                {String(card.question ?? '')}
              </Response>
              <div className="mt-2 text-sm text-muted-foreground">
                <Response className="text-sm">
                  {String(card.answer ?? '')}
                </Response>
              </div>
            </div>
          ))}
        </div>
      )
    }
    return (
      <div className="flex flex-1 items-center justify-center min-h-screen gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载闪卡...</span>
      </div>
    )
  }

  // Session is complete when queue is empty
  if (state.queue.length === 0 || state.isCompleted) {
    return (
      <FlashcardCompletionScreen
        onSubmit={onSubmit}
        onRetry={onRetry}
        onRetryWrong={onRetryWrong}
        onClose={onClose}
        flashcardGroupId={flashcardGroupId}
        projectId={projectId}
      />
    )
  }

  return (
    <div className="flex flex-col space-y-12 flex-1 min-h-0 overflow-auto p-4">
      <FlashcardProgress flashcardGroupId={flashcardGroupId} />

      {Result.builder(currentCard)
        .onSuccess((card) =>
          card ? (
            <FlashcardCard
              flashcardGroupId={flashcardGroupId}
              question={card.question}
              answer={card.answer}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-muted-foreground">没有可用闪卡</p>
            </div>
          ),
        )
        .onInitialOrWaiting(() => (
          <div className="flex flex-1 items-center justify-center">
            <Loader2Icon className="size-4 animate-spin" />
            <span>正在加载闪卡...</span>
          </div>
        ))
        .render()}

      <FlashcardControls
        flashcardGroupId={flashcardGroupId}
        projectId={projectId}
      />
    </div>
  )
}
