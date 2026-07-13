import { useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import React, { useEffect } from 'react'
import { QuizContent } from './quiz-content'
import {
  goToNextQuestionAtom,
  goToPreviousQuestionAtom,
  quizDetailStateAtom,
  resetQuizAtom,
  setSelectedAnswerAtom,
  submitQuizQuestionAtom,
} from '@/data-acess/quiz-detail-state'
import { quizQuestionsAtom } from '@/data-acess/quiz'

type Props = React.ComponentProps<'div'> & {
  quizId: string
  projectId: string
}

export const QuizDetail = ({ quizId, projectId, ...props }: Props) => {
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))

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

      const state = Option.isSome(stateResult) ? stateResult.value : null
      if (!state) return

      // Don't handle shortcuts when showing results
      if (state.showResults) return

      const questions =
        questionsResult._tag === 'Success' ? questionsResult.value : null
      if (!questions) return

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

  return (
    <div className="flex flex-col flex-1 min-h-0" {...props}>
      <QuizContent quizId={quizId} projectId={projectId} />
    </div>
  )
}
