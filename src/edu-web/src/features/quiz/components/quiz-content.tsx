import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { Loader2Icon } from 'lucide-react'
import { QuizControls } from './quiz-controls'
import { QuizProgress } from './quiz-progress'
import { QuizQuestionCard } from './quiz-question-card'
import { QuizResultsView } from './quiz-results-view'
import { quizQuestionsAtom } from '@/data-acess/quiz'
import { quizDetailStateAtom } from '@/data-acess/quiz-detail-state'

type QuizContentProps = {
  quizId: string
  projectId: string
}

export const QuizContent = ({ quizId, projectId }: QuizContentProps) => {
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))

  return Result.builder(questionsResult)
    .onInitialOrWaiting(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载题目...</span>
      </div>
    ))
    .onFailure(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-destructive">
        <span>题目加载失败</span>
      </div>
    ))
    .onSuccess((quizQuestions) => {
      const state = Option.isSome(stateResult) ? stateResult.value : null
      if (!state) return null

      if (quizQuestions.length === 0) {
        return (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            没有题目
          </div>
        )
      }

      if (state.showResults) {
        return <QuizResultsView quizId={quizId} projectId={projectId} />
      }

      return (
        <div className="flex min-h-0 flex-1 overflow-auto bg-muted/25 p-3 sm:p-5 lg:p-7">
          <div className="mx-auto flex min-h-[680px] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-border/90 bg-card shadow-[0_12px_36px_rgba(23,70,120,0.08)] md:flex-row">
            <QuizProgress quizId={quizId} projectId={projectId} />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <div className="min-h-0 flex-1 overflow-y-auto">
                <QuizQuestionCard quizId={quizId} projectId={projectId} />
              </div>

              <QuizControls quizId={quizId} projectId={projectId} />
            </div>
          </div>
        </div>
      )
    })
    .render()
}
