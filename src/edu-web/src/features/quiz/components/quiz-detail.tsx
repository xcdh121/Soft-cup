import { useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import { Loader2Icon, RefreshCwIcon } from 'lucide-react'
import React, { useEffect, useRef } from 'react'
import { QuizContent } from './quiz-content'
import type { QuizQuestionDto } from '@/integrations/api/client'
import {
  goToNextQuestionAtom,
  goToPreviousQuestionAtom,
  quizDetailStateAtom,
  setSelectedAnswerAtom,
  submitQuizQuestionAtom,
} from '@/data-acess/quiz-detail-state'
import {
  quizAtom,
  quizQuestionsAtom,
  refreshQuizQuestionsAtom,
} from '@/data-acess/quiz'
import { cn } from '@/lib/utils'
import { useGeneratedResourceSnapshot } from '@/hooks/use-generated-resource-snapshot'
import { readLearningVerification } from '@/lib/learning-verification-context'
import { Button } from '@/components/ui/button'

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
  const quizResult = useAtomValue(quizAtom(`${projectId}:${quizId}`))
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const quizName = quizResult._tag === 'Success' ? quizResult.value.name : ''
  const isGeneratedReinforcementQuiz =
    /^(巩固选择题|reinforcement quiz)\s*[:：]/i.test(quizName)
  const refreshQuestions = useAtomSet(refreshQuizQuestionsAtom, {
    mode: 'promise',
  })
  const snapshot = useGeneratedResourceSnapshot<Array<QuizQuestionDto>>({
    projectId,
    targetType: 'quiz',
    targetId: quizId,
    dataPath: `/api/v1/projects/${projectId}/quizzes/${quizId}/questions`,
    pollWhenEmpty: isGeneratedReinforcementQuiz,
  })

  const setSelectedAnswer = useAtomSet(setSelectedAnswerAtom, {
    mode: 'promise',
  })
  const goToNext = useAtomSet(goToNextQuestionAtom, { mode: 'promise' })
  const goToPrevious = useAtomSet(goToPreviousQuestionAtom, { mode: 'promise' })
  const submitQuestion = useAtomSet(submitQuizQuestionAtom, { mode: 'promise' })
  const wasGenerating = useRef(false)
  const verificationContext = readLearningVerification(projectId)

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
    if (snapshot.checking) return
    if (snapshot.isGenerating) {
      wasGenerating.current = true
      return
    }
    if (!wasGenerating.current) return
    wasGenerating.current = false
    void refreshQuestions({ projectId, quizId })
  }, [
    projectId,
    quizId,
    refreshQuestions,
    snapshot.checking,
    snapshot.isGenerating,
  ])

  const isEmpty =
    questionsResult._tag === 'Success' && questionsResult.value.length === 0

  const loadedQuestionCount =
    questionsResult._tag === 'Success' ? questionsResult.value.length : 0
  const snapshotQuestions = snapshot.data ?? []
  const showIncrementalGeneration =
    snapshot.checking ||
    snapshot.isGenerating ||
    (snapshot.isManaged &&
      snapshotQuestions.length > 0 &&
      loadedQuestionCount < snapshotQuestions.length)

  if (
    isGeneratedReinforcementQuiz &&
    isEmpty &&
    snapshotQuestions.length === 0 &&
    (snapshot.status === 'failed' || snapshot.timedOut)
  ) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="font-medium">
          {snapshot.status === 'failed'
            ? '选择题生成失败'
            : '选择题生成时间较长'}
        </div>
        <p className="max-w-md text-sm text-muted-foreground">
          {snapshot.status === 'failed'
            ? '本次生成任务未能完成，请返回学习计划重新生成，或稍后重试。'
            : '任务可能仍在队列中。你可以稍后再来，或立即重新检查生成结果。'}
        </p>
        <Button type="button" variant="outline" onClick={snapshot.retry}>
          <RefreshCwIcon className="size-4" /> 重新检查
        </Button>
      </div>
    )
  }

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
              className="rounded-xl border bg-card p-4 text-card-foreground"
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
      {verificationContext && (
        <div
          className="mx-4 mt-4 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm"
          role="status"
        >
          <div className="font-medium">当前为干预效果验证</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {verificationContext.objective}
            。提交第一道与目标知识点匹配的题目后，将记录为验证证据并计算掌握度增益。
          </div>
        </div>
      )}
      <QuizContent quizId={quizId} projectId={projectId} />
    </div>
  )
}
