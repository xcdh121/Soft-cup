import { Atom, Registry, Result } from '@effect-atom/atom-react'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Data, Effect, Layer, Option } from 'effect'
import {
  practiceRecordsRemoteAtom,
  submitPracticeRecordsBatchAtom,
} from './practice'
import { quizQuestionsAtom } from './quiz'
import { knowledgeGraphAtom } from './knowledge-graph'
import { closedLoopOverviewAtom } from './learning-closed-loop'
import {
  latestStudyPlanRemoteAtom,
  studyPlansHistoryRemoteAtom,
} from './study-plan'
import type { PracticeRecordCreate, QuizQuestionDto } from '@/integrations/api'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import {
  consumeLearningVerification,
  readLearningVerification,
} from '@/lib/learning-verification-context'
import type { LearningVerificationContext } from '@/lib/learning-verification-context'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type QuizOption = 'A' | 'B' | 'C' | 'D'

const quizOptions: ReadonlyArray<QuizOption> = ['A', 'B', 'C', 'D']

/**
 * Generated questions are not fully consistent: correct_option can be `a`,
 * `A. answer text`, or the answer text itself. Always reduce it to the option
 * key so grading never depends on wording differences.
 */
export const getQuizCorrectOption = (
  question: Pick<
    QuizQuestionDto,
    'correct_option' | 'option_a' | 'option_b' | 'option_c' | 'option_d'
  >,
): QuizOption | null => {
  const rawAnswer = question.correct_option.trim()
  const explicitOption = rawAnswer.match(
    /^(?:选项\s*)?([A-D])(?:\s*[.、:：)）\]-]|$)/i,
  )?.[1]
  if (explicitOption) return explicitOption.toUpperCase() as QuizOption

  const normalizedAnswer = rawAnswer.replace(/\s+/g, ' ').trim().toLowerCase()
  const optionText: Record<QuizOption, string> = {
    A: question.option_a,
    B: question.option_b,
    C: question.option_c,
    D: question.option_d,
  }

  const optionFromDescription = quizOptions.find(
    (option) =>
      optionText[option].replace(/\s+/g, ' ').trim().toLowerCase() ===
      normalizedAnswer,
  )
  if (optionFromDescription) return optionFromDescription

  const looselyPrefixedOption = rawAnswer.match(/^([A-D])\s+.+$/i)?.[1]
  return looselyPrefixedOption
    ? (looselyPrefixedOption.toUpperCase() as QuizOption)
    : null
}

export const buildQuizPracticeRecord = ({
  question,
  userAnswer,
  quizId,
  verification,
}: {
  question: QuizQuestionDto
  userAnswer: QuizOption
  quizId: string
  verification: LearningVerificationContext | null
}) => {
  const correctOption = getQuizCorrectOption(question)
  const correctAnswer = correctOption ?? question.correct_option.trim()
  return {
    item_type: 'quiz' as const,
    item_id: question.id,
    knowledge_point_id: question.knowledge_point_id,
    topic: extractTopic(question.question_text),
    user_answer: userAnswer,
    correct_answer: correctAnswer,
    was_correct: correctOption === userAnswer,
    score: correctOption === userAnswer ? 1 : 0,
    answer_mode: 'quiz',
    mapping_method: question.knowledge_point_id ? 'explicit' : undefined,
    recommendation_id: verification?.recommendationId,
    learning_path_id: verification?.learningPathId,
    learning_path_step_id: verification?.learningPathStepId,
    is_verification: verification !== null,
    // A quiz is a first-class resource, but it is not a generated_resources
    // row. Keep its id in metadata instead of violating resource_id's FK.
    metadata: verification
      ? {
          quiz_id: quizId,
          verification_objective: verification.objective,
        }
      : { quiz_id: quizId },
  }
}

export type QuizDetailState = {
  readonly currentQuestionIndex: number
  readonly showResults: boolean
  readonly pendingPracticeRecords: Record<string, PracticeRecordCreate>
  readonly selectedByQuestionId: Partial<Record<string, QuizOption>>
  readonly submittedByQuestionId: Partial<Record<string, boolean>>
}

type QuizDetailAction = Data.TaggedEnum<{
  SetCurrentQuestionIndex: { readonly index: number }
  SetShowResults: { readonly show: boolean }
  SetSelectedAnswer: {
    readonly questionId: string
    readonly option: QuizOption
  }
  MarkQuestionSubmitted: { readonly questionId: string }
  SetPendingPracticeRecords: {
    readonly practiceRecords: Record<string, PracticeRecordCreate>
  }
  Reset: {}
  ClearPracticeRecords: {}
}>

const QuizDetailAction = Data.taggedEnum<QuizDetailAction>()

const initialState: QuizDetailState = {
  currentQuestionIndex: 0,
  showResults: false,
  pendingPracticeRecords: {},
  selectedByQuestionId: {},
  submittedByQuestionId: {},
}

const QUIZ_PROGRESS_STORAGE_PREFIX = 'edu.quiz-progress.v1'

const getQuizProgressStorage = (): Storage | null => {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

const quizProgressStorageKey = (quizId: string) =>
  `${QUIZ_PROGRESS_STORAGE_PREFIX}:${quizId}`

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

export const readQuizDetailProgress = (
  quizId: string,
): QuizDetailState | null => {
  const storage = getQuizProgressStorage()
  if (!storage) return null
  try {
    const value = storage.getItem(quizProgressStorageKey(quizId))
    if (!value) return null
    const parsed: unknown = JSON.parse(value)
    if (!isRecord(parsed)) throw new Error('Invalid saved quiz progress')
    const stored = parsed as Partial<QuizDetailState>
    return {
      ...initialState,
      ...stored,
      currentQuestionIndex:
        Number.isInteger(stored.currentQuestionIndex) &&
        Number(stored.currentQuestionIndex) >= 0
          ? Number(stored.currentQuestionIndex)
          : 0,
      showResults: stored.showResults === true,
      pendingPracticeRecords: isRecord(stored.pendingPracticeRecords)
        ? stored.pendingPracticeRecords
        : {},
      selectedByQuestionId: isRecord(stored.selectedByQuestionId)
        ? stored.selectedByQuestionId
        : {},
      submittedByQuestionId: isRecord(stored.submittedByQuestionId)
        ? stored.submittedByQuestionId
        : {},
    }
  } catch {
    storage.removeItem(quizProgressStorageKey(quizId))
    return null
  }
}

export const persistQuizDetailProgress = (
  quizId: string,
  state: QuizDetailState,
) => {
  const storage = getQuizProgressStorage()
  if (!storage) return
  try {
    storage.setItem(quizProgressStorageKey(quizId), JSON.stringify(state))
  } catch {
    // Losing browser storage must not interrupt an active quiz attempt.
  }
}

export const quizDetailStateAtom = Atom.family((quizId: string) =>
  Object.assign(
    Atom.writable(
      (get: Atom.Context) => {
        const result = get.self<QuizDetailState>()
        if (Option.isNone(result)) {
          return Option.some(readQuizDetailProgress(quizId) ?? initialState)
        }
        const stored = result.value as Partial<QuizDetailState>
        return Option.some({
          ...initialState,
          ...stored,
          selectedByQuestionId: stored.selectedByQuestionId ?? {},
          submittedByQuestionId: stored.submittedByQuestionId ?? {},
        })
      },
      (ctx, action: QuizDetailAction) => {
        const result = ctx.get(quizDetailStateAtom(quizId))
        if (Option.isNone(result)) return

        const update = QuizDetailAction.$match(action, {
          SetCurrentQuestionIndex: ({ index }) => {
            return { ...result.value, currentQuestionIndex: index }
          },
          SetShowResults: ({ show }) => {
            return { ...result.value, showResults: show }
          },
          SetSelectedAnswer: ({ questionId, option }) => {
            if (result.value.submittedByQuestionId[questionId]) {
              return result.value
            }
            return {
              ...result.value,
              selectedByQuestionId: {
                ...result.value.selectedByQuestionId,
                [questionId]: option,
              },
            }
          },
          MarkQuestionSubmitted: ({ questionId }) => ({
            ...result.value,
            submittedByQuestionId: {
              ...result.value.submittedByQuestionId,
              [questionId]: true,
            },
          }),
          SetPendingPracticeRecords: ({ practiceRecords }) => {
            return { ...result.value, pendingPracticeRecords: practiceRecords }
          },
          Reset: () => {
            return initialState
          },
          ClearPracticeRecords: () => {
            return { ...result.value, pendingPracticeRecords: {} }
          },
        })

        persistQuizDetailProgress(quizId, update)
        ctx.setSelf(Option.some(update))
      },
    ),
    {
      initial: initialState,
    },
  ),
)

export const quizStatsAtom = Atom.family((input: string) => {
  const [projectId, quizId] = input.split(':')
  return Atom.make(
    // Effect.fn supplies the atom getter to this synchronous selector.
    // eslint-disable-next-line require-yield
    Effect.fn(function* (get) {
      const state = get(quizDetailStateAtom(quizId))
      if (Option.isNone(state))
        return { total: 0, correct: 0, incorrect: 0, percentage: 0 }

      if (!state.value.showResults)
        return { total: 0, correct: 0, incorrect: 0, percentage: 0 }

      const questionsResult = get(quizQuestionsAtom(`${projectId}:${quizId}`))
      if (!Result.isSuccess(questionsResult))
        return { total: 0, correct: 0, incorrect: 0, percentage: 0 }

      const quizQuestions = questionsResult.value
      const { selectedByQuestionId } = state.value

      const total = quizQuestions.length
      const correct = quizQuestions.reduce((acc, q) => {
        return (
          acc + (selectedByQuestionId[q.id] === getQuizCorrectOption(q) ? 1 : 0)
        )
      }, 0)
      const incorrect = total - correct
      const percentage = total > 0 ? Math.round((correct / total) * 100) : 0

      return { total, correct, incorrect, percentage }
    }),
  )
})

export const currentQuestionAtom = Atom.family((input: string) => {
  const [projectId, quizId] = input.split(':')
  return Atom.make(
    // Effect.fn supplies the atom getter to this synchronous selector.
    // eslint-disable-next-line require-yield
    Effect.fn(function* (get) {
      const state = get(quizDetailStateAtom(quizId))
      if (Option.isNone(state)) return null

      const questionsResult = get(quizQuestionsAtom(`${projectId}:${quizId}`))
      if (!Result.isSuccess(questionsResult)) return null

      const quizQuestions = questionsResult.value
      const { currentQuestionIndex } = state.value

      return quizQuestions[currentQuestionIndex] ?? null
    }),
  )
})

export const canSubmitQuizAtom = Atom.family((input: string) => {
  const [projectId, quizId] = input.split(':')
  return Atom.make(
    // Effect.fn supplies the atom getter to this synchronous selector.
    // eslint-disable-next-line require-yield
    Effect.fn(function* (get) {
      const state = get(quizDetailStateAtom(quizId))
      if (Option.isNone(state)) return false

      const questionsResult = get(quizQuestionsAtom(`${projectId}:${quizId}`))
      if (!Result.isSuccess(questionsResult)) return false

      const quizQuestions = questionsResult.value
      const { submittedByQuestionId } = state.value

      return quizQuestions.every(
        (question) => submittedByQuestionId[question.id],
      )
    }),
  )
})

export const setCurrentQuestionIndexAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string; index: number }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetCurrentQuestionIndex({ index: input.index }),
    )
  }),
)

export const setShowResultsAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string; show: boolean }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetShowResults({ show: input.show }),
    )
  }),
)

export const setSelectedAnswerAtom = runtime.fn(
  Effect.fn(function* (input: {
    quizId: string
    questionId: string
    option: QuizOption
  }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetSelectedAnswer({
        questionId: input.questionId,
        option: input.option,
      }),
    )
  }),
)

export const submitQuizQuestionAtom = runtime.fn(
  Effect.fn(function* (input: {
    projectId: string
    quizId: string
    questionId: string
  }) {
    const registry = yield* Registry.AtomRegistry
    const { apiClient } = yield* ApiClientService
    const stateResult = registry.get(quizDetailStateAtom(input.quizId))
    if (Option.isNone(stateResult)) return false

    const state = stateResult.value
    if (state.submittedByQuestionId[input.questionId]) return true

    const userAnswer = state.selectedByQuestionId[input.questionId]
    if (!userAnswer) return false

    const questionsResult = registry.get(
      quizQuestionsAtom(`${input.projectId}:${input.quizId}`),
    )
    if (!Result.isSuccess(questionsResult)) return false

    const question = questionsResult.value.find(
      (candidate) => candidate.id === input.questionId,
    )
    if (!question) return false

    const savedVerification = readLearningVerification(input.projectId)
    const verification =
      savedVerification?.knowledgePointId === question.knowledge_point_id
        ? savedVerification
        : null
    const practiceRecord = buildQuizPracticeRecord({
      question,
      userAnswer,
      quizId: input.quizId,
      verification,
    })
    yield* apiClient.createPracticeRecordApiV1ProjectsProjectIdPracticeRecordsPost(
      input.projectId,
      practiceRecord,
    )
    if (practiceRecord.is_verification) {
      consumeLearningVerification(input.projectId, question.knowledge_point_id)
      registry.refresh(closedLoopOverviewAtom(input.projectId))
      registry.refresh(latestStudyPlanRemoteAtom(input.projectId))
      registry.refresh(studyPlansHistoryRemoteAtom(input.projectId))
    }

    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.MarkQuestionSubmitted({ questionId: question.id }),
    )
    registry.refresh(practiceRecordsRemoteAtom(input.projectId))
    registry.refresh(knowledgeGraphAtom(input.projectId))
    return true
  }),
)

export const setPendingPracticeRecordsAtom = runtime.fn(
  Effect.fn(function* (input: {
    quizId: string
    practiceRecords: Record<string, PracticeRecordCreate>
  }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetPendingPracticeRecords({
        practiceRecords: input.practiceRecords,
      }),
    )
  }),
)

export const resetQuizAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(quizDetailStateAtom(input.quizId), QuizDetailAction.Reset())
  }),
)

export const clearPracticeRecordsAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string }) {
    const registry = yield* Registry.AtomRegistry
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.ClearPracticeRecords(),
    )
  }),
)

const extractTopic = (text: string, maxLength = 100): string => {
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
}

export const submitQuizAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; quizId: string }) {
    const registry = yield* Registry.AtomRegistry

    const currentStateResult = registry.get(quizDetailStateAtom(input.quizId))
    if (Option.isNone(currentStateResult)) return

    const currentState = currentStateResult.value
    const { selectedByQuestionId } = currentState

    const questionsResult = registry.get(
      quizQuestionsAtom(`${input.projectId}:${input.quizId}`),
    )
    if (!Result.isSuccess(questionsResult)) return

    const quizQuestions = questionsResult.value

    // Track ALL practice records (both correct and incorrect) for adaptive learning
    const practiceRecords: Record<string, PracticeRecordCreate> = {}

    for (const q of quizQuestions) {
      const userAnswer = selectedByQuestionId[q.id]
      const correctOption = getQuizCorrectOption(q)

      // Track all practice records, not just mistakes
      if (userAnswer) {
        const wasCorrect = userAnswer === correctOption
        practiceRecords[q.id] = {
          item_type: 'quiz',
          item_id: q.id,
          knowledge_point_id: q.knowledge_point_id,
          topic: extractTopic(q.question_text),
          user_answer: userAnswer,
          correct_answer: correctOption ?? q.correct_option.trim(),
          was_correct: wasCorrect,
        }
      }
    }

    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetShowResults({ show: true }),
    )
    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetPendingPracticeRecords({ practiceRecords }),
    )
  }),
)

export const submitPendingPracticeRecordsAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string; projectId: string }) {
    const registry = yield* Registry.AtomRegistry

    const currentStateResult = registry.get(quizDetailStateAtom(input.quizId))
    if (Option.isNone(currentStateResult)) return

    const currentState = currentStateResult.value
    const pendingPracticeRecords = Object.values(
      currentState.pendingPracticeRecords,
    )
    if (pendingPracticeRecords.length === 0) return

    registry.set(submitPracticeRecordsBatchAtom, {
      projectId: input.projectId,
      practice_records: pendingPracticeRecords as unknown as [
        PracticeRecordCreate,
        ...Array<PracticeRecordCreate>,
      ],
    })

    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.ClearPracticeRecords(),
    )
  }),
)

export const goToNextQuestionAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; quizId: string }) {
    const registry = yield* Registry.AtomRegistry

    const currentStateResult = registry.get(quizDetailStateAtom(input.quizId))
    if (Option.isNone(currentStateResult)) return
    const currentState = currentStateResult.value

    const { currentQuestionIndex } = currentState

    const questionsResult = registry.get(
      quizQuestionsAtom(`${input.projectId}:${input.quizId}`),
    )
    if (!Result.isSuccess(questionsResult)) return

    const quizQuestions = questionsResult.value
    if (currentQuestionIndex >= quizQuestions.length) return
    const currentQuestion = quizQuestions[currentQuestionIndex]
    if (!currentState.submittedByQuestionId[currentQuestion.id]) {
      return
    }
    const isLastQuestion = currentQuestionIndex === quizQuestions.length - 1

    if (isLastQuestion) return

    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetCurrentQuestionIndex({
        index: currentQuestionIndex + 1,
      }),
    )
  }),
)

export const goToPreviousQuestionAtom = runtime.fn(
  Effect.fn(function* (input: { quizId: string }) {
    const registry = yield* Registry.AtomRegistry

    const currentStateResult = registry.get(quizDetailStateAtom(input.quizId))
    if (Option.isNone(currentStateResult)) return
    const currentState = currentStateResult.value

    const { currentQuestionIndex } = currentState

    const isFirstQuestion = currentQuestionIndex === 0
    if (isFirstQuestion) return

    registry.set(
      quizDetailStateAtom(input.quizId),
      QuizDetailAction.SetCurrentQuestionIndex({
        index: currentQuestionIndex - 1,
      }),
    )
  }),
)
