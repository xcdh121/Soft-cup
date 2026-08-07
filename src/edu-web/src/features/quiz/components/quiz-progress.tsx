import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { CheckIcon } from 'lucide-react'

import { quizQuestionsAtom } from '@/data-acess/quiz'
import {
  quizDetailStateAtom,
  setCurrentQuestionIndexAtom,
} from '@/data-acess/quiz-detail-state'
import { cn } from '@/lib/utils'

type QuizProgressProps = {
  quizId: string
  projectId: string
}

export const QuizProgress = ({ quizId, projectId }: QuizProgressProps) => {
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )
  const setCurrentQuestionIndex = useAtomSet(setCurrentQuestionIndexAtom, {
    mode: 'promise',
  })

  const state = Option.isSome(stateResult) ? stateResult.value : null
  const questions = Result.isSuccess(questionsResult)
    ? questionsResult.value
    : []

  if (!state || questions.length === 0) return null

  const submittedCount = questions.filter(
    (question) => state.submittedByQuestionId[question.id],
  ).length

  return (
    <aside className="w-full shrink-0 border-b border-border/80 bg-muted/20 md:w-32 md:border-r md:border-b-0">
      <div className="hidden h-12 items-center justify-center border-b border-border/70 text-sm font-medium text-muted-foreground md:flex">
        题目导航
      </div>

      <div className="flex items-center gap-4 px-4 py-3 md:flex-col md:gap-4 md:px-3 md:py-5">
        <div className="shrink-0 text-sm text-muted-foreground">
          <span className="text-xl font-semibold text-foreground">
            {submittedCount}
          </span>
          /{questions.length} 题
        </div>

        <nav
          aria-label="选择题目"
          className="flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1 md:w-full md:flex-col md:items-center md:overflow-visible md:pb-0"
        >
          {questions.map((question, index) => {
            const isCurrent = index === state.currentQuestionIndex
            const isSubmitted = Boolean(
              state.submittedByQuestionId[question.id],
            )
            const hasAnswer = Boolean(state.selectedByQuestionId[question.id])

            return (
              <button
                key={question.id}
                type="button"
                aria-current={isCurrent ? 'step' : undefined}
                aria-label={`第 ${index + 1} 题${isSubmitted ? '，已提交' : hasAnswer ? '，已选择答案' : ''}`}
                onClick={() => void setCurrentQuestionIndex({ quizId, index })}
                className={cn(
                  'relative flex size-11 shrink-0 items-center justify-center rounded-lg border text-base font-medium transition-all md:size-14',
                  isCurrent
                    ? 'border-primary bg-primary text-primary-foreground shadow-[0_7px_18px_rgba(23,104,201,0.2)]'
                    : isSubmitted
                      ? 'border-primary/55 bg-primary/[0.06] text-primary hover:bg-primary/10'
                      : hasAnswer
                        ? 'border-warning/55 bg-warning/10 text-warning-foreground hover:bg-warning/15'
                        : 'border-border bg-card text-muted-foreground hover:border-primary/35 hover:text-primary',
                )}
              >
                {index + 1}
                {isSubmitted ? (
                  <span className="absolute -right-1.5 -bottom-1.5 flex size-5 items-center justify-center rounded-full border-2 border-card bg-[#18a66a] text-white">
                    <CheckIcon className="size-3" strokeWidth={3} />
                  </span>
                ) : null}
              </button>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
