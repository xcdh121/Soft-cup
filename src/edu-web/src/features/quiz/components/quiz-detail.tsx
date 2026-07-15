import { useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { Loader2Icon } from 'lucide-react'
import React, { useEffect } from 'react'
import { QuizContent } from './quiz-content'
import type { QuizQuestionDto } from '@/integrations/api/client'
import {
  goToNextQuestionAtom,
  goToPreviousQuestionAtom,
  quizDetailStateAtom,
  resetQuizAtom,
  setSelectedAnswerAtom,
  submitQuizQuestionAtom,
} from '@/data-acess/quiz-detail-state'
import { quizQuestionsAtom, refreshQuizQuestionsAtom } from '@/data-acess/quiz'
import { cn } from '@/lib/utils'
import { useGeneratedResourceSnapshot } from '@/hooks/use-generated-resource-snapshot'

type Props = React.ComponentProps<'div'> & {
  quizId: string
  projectId: string
}

export const QuizDetail = ({
  quizId,
  projectId,
  className,
  ...props
}: Props) => {
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const refreshQuestions = useAtomSet(refreshQuizQuestionsAtom, {
    mode: 'promise',
  })
  const snapshot = useGeneratedResourceSnapshot<Array<QuizQuestionDto>>({
    projectId,
    targetType: 'quiz',
    targetId: quizId,
    dataPath: `/api/v1/projects/${projectId}/quizzes/${quizId}/questions`,
  })

  const resetQuiz = useAtomSet(resetQuizAtom)
  const setSelectedAnswer = useAtomSet(setSelectedAnswerAtom, {
    mode: 'promise',
  })
  const goToNext = useAtomSet(goToNextQuestionAtom, { mode: 'promise' })
  const goToPrevious = useAtomSet(goToPreviousQuestionAtom, { mode: 'promise' })
  const submitQuestion = useAtomSet(submitQuizQuestionAtom, { mode: 'promise' })

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if user is typing in an input/textarea
      const target = event.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return
      }

      if (Option.isNone(stateResult)) return
      const state = stateResult.value

      // Don't handle shortcuts when showing results
      if (state.showResults) return

      const questions =
        questionsResult._tag === 'Success' ? questionsResult.value : null
      if (!questions) return
      if (questions.length === 0) return

      const currentQuestion = questions[state.currentQuestionIndex]
      const isCurrentSubmitted = Boolean(
        state.submittedByQuestionId[currentQuestion.id],
      )

      // Arrow keys for navigation
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        if (event.key === 'ArrowLeft') {
          goToPrevious({ quizId })
        } else {
          goToNext({ quizId, projectId })
        }
        return
      }

      // Number keys for selecting answers (1-4 for A-D)
      if (event.key >= '1' && event.key <= '4') {
        if (isCurrentSubmitted) return
        event.preventDefault()
        const option = ['A', 'B', 'C', 'D'][parseInt(event.key) - 1] as
          | 'A'
          | 'B'
          | 'C'
          | 'D'
        setSelectedAnswer({
          quizId,
          questionId: currentQuestion.id,
          option,
        })
        return
      }

      // Enter submits and grades the current question.
      if (event.key === 'Enter') {
        if (
          !isCurrentSubmitted &&
          state.selectedByQuestionId[currentQuestion.id]
        ) {
          event.preventDefault()
          submitQuestion({ quizId, projectId, questionId: currentQuestion.id })
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    quizId,
    stateResult,
    questionsResult,
    setSelectedAnswer,
    goToNext,
    goToPrevious,
    submitQuestion,
  ])

  useEffect(() => {
    resetQuiz({ quizId })
  }, [quizId, resetQuiz])

  useEffect(() => {
    if (snapshot.checking || snapshot.isGenerating) return
    void refreshQuestions({ projectId, quizId })
  }, [
    projectId,
    quizId,
    refreshQuestions,
    snapshot.checking,
    snapshot.isGenerating,
  ])

  const loadedQuestionCount =
    questionsResult._tag === 'Success' ? questionsResult.value.length : 0
  const snapshotQuestions = snapshot.data ?? []
  const showIncrementalGeneration =
    snapshot.checking ||
    snapshot.isGenerating ||
    (snapshot.isManaged &&
      snapshotQuestions.length > 0 &&
      loadedQuestionCount < snapshotQuestions.length)

  if (showIncrementalGeneration) {
    return (
      <div
        {...props}
        className={cn(
          'flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4',
          className,
        )}
      >
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2Icon className="size-4 animate-spin" />
          <span>
            {snapshot.checking
              ? '正在加载测验…'
              : snapshotQuestions.length > 0
                ? `已生成 ${snapshotQuestions.length} 道题，后续题目正在生成…`
                : '正在生成第一道题…'}
          </span>
        </div>
        <div className="space-y-3">
          {snapshotQuestions.map((question, index) => (
            <div
              key={question.id}
              className="rounded-xl border bg-background p-4"
            >
              <div className="font-medium">
                {index + 1}. {question.question_text}
              </div>
              <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                <span>A. {question.option_a}</span>
                <span>B. {question.option_b}</span>
                <span>C. {question.option_c}</span>
                <span>D. {question.option_d}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div {...props} className={cn('flex min-h-0 flex-1 flex-col', className)}>
      <QuizContent quizId={quizId} projectId={projectId} />
    </div>
  )
}
