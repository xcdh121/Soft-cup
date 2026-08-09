import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { quizQuestionsAtom } from '@/data-acess/quiz'
import {
  canSubmitQuizAtom,
  goToNextQuestionAtom,
  goToPreviousQuestionAtom,
  quizDetailStateAtom,
  setShowResultsAtom,
  submitQuizQuestionAtom,
} from '@/data-acess/quiz-detail-state'

type QuizControlsProps = {
  quizId: string
  projectId: string
}

export const QuizControls = ({ quizId, projectId }: QuizControlsProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )
  const canSubmitResult = useAtomValue(
    canSubmitQuizAtom(`${projectId}:${quizId}`),
  )

  const goToNext = useAtomSet(goToNextQuestionAtom, { mode: 'promise' })
  const goToPrevious = useAtomSet(goToPreviousQuestionAtom, { mode: 'promise' })
  const submitQuestion = useAtomSet(submitQuizQuestionAtom, { mode: 'promise' })
  const setShowResults = useAtomSet(setShowResultsAtom, { mode: 'promise' })

  const state = Option.isSome(stateResult) ? stateResult.value : null
  if (!state) return null

  const questions = Result.isSuccess(questionsResult)
    ? questionsResult.value
    : []
  const canSubmit = Result.isSuccess(canSubmitResult)
    ? canSubmitResult.value
    : false

  const currentIndex = state.currentQuestionIndex
  const totalQuestions = questions.length
  const showResults = state.showResults
  const currentQuestion = questions[currentIndex]

  const handleNext = async () => {
    await goToNext({ quizId, projectId })
  }

  const handlePrevious = async () => {
    await goToPrevious({ quizId })
  }

  const isCurrentSubmitted = Boolean(
    state.submittedByQuestionId[currentQuestion.id],
  )

  const handleSubmitQuestion = async () => {
    setIsSubmitting(true)
    try {
      const submitted = await submitQuestion({
        quizId,
        projectId,
        questionId: currentQuestion.id,
      })
      if (!submitted) {
        toast.error('提交失败，请重新选择答案后再试。')
      }
    } catch {
      toast.error('答案提交失败，请稍后重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleShowResults = async () => {
    await setShowResults({ quizId, show: true })
  }

  if (showResults) return null

  return (
    <div className="sticky bottom-0 z-10 flex items-center justify-center border-t bg-background/95 px-4 py-4 shadow-[0_-8px_24px_-20px_rgba(0,0,0,0.5)] backdrop-blur">
      <div className="flex flex-wrap justify-center gap-4">
        <Button
          onClick={handlePrevious}
          disabled={currentIndex === 0}
          variant="outline"
          className="flex items-center gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          上一题
        </Button>

        {!isCurrentSubmitted ? (
          <Button
            onClick={handleSubmitQuestion}
            disabled={
              isSubmitting || !state.selectedByQuestionId[currentQuestion.id]
            }
            size="lg"
            className="px-8"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="size-4 animate-spin" /> 提交中…
              </>
            ) : (
              '提交本题'
            )}
          </Button>
        ) : currentIndex === totalQuestions - 1 ? (
          <Button
            onClick={handleShowResults}
            disabled={!canSubmit}
            size="lg"
            className="px-8"
          >
            查看结果
          </Button>
        ) : (
          <Button
            onClick={handleNext}
            disabled={!isCurrentSubmitted}
            variant="default"
            className="flex items-center gap-2"
          >
            下一题
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
