import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { ChevronLeft, ChevronRight } from 'lucide-react'
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
    await submitQuestion({ quizId, projectId, questionId: currentQuestion.id })
  }

  const handleShowResults = async () => {
    await setShowResults({ quizId, show: true })
  }

  if (showResults) return null

  return (
    <div className="sticky bottom-0 z-10 border-t border-border/80 bg-card/95 px-4 py-3 backdrop-blur sm:px-8">
      <div className="grid grid-cols-3 items-center gap-3">
        <Button
          onClick={handlePrevious}
          disabled={currentIndex === 0}
          variant="ghost"
          className="justify-self-start px-2 text-muted-foreground hover:text-primary sm:px-4"
        >
          <ChevronLeft className="h-4 w-4" />
          上一题
        </Button>

        {!isCurrentSubmitted ? (
          <Button
            onClick={handleSubmitQuestion}
            disabled={!state.selectedByQuestionId[currentQuestion.id]}
            className="min-w-24 justify-self-center px-5 sm:min-w-32"
          >
            提交本题
          </Button>
        ) : (
          <span className="min-w-24 justify-self-center rounded-lg bg-muted px-5 py-2 text-center text-sm text-muted-foreground sm:min-w-32">
            已提交
          </span>
        )}

        {currentIndex === totalQuestions - 1 ? (
          <Button
            onClick={handleShowResults}
            disabled={!canSubmit}
            variant="ghost"
            className="justify-self-end px-2 hover:text-primary sm:px-4"
          >
            查看结果
          </Button>
        ) : (
          <Button
            onClick={handleNext}
            disabled={!isCurrentSubmitted}
            variant="ghost"
            className="justify-self-end px-2 hover:text-primary sm:px-4"
          >
            下一题
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
