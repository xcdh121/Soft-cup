import { Atom } from '@effect-atom/atom-react'
import { Effect } from 'effect'
import { ApiClientService } from '@/integrations/api/http'

export type EvaluationResource = {
  id: string
  type: 'quiz' | 'flashcard'
  name: string
  description?: string | null
  createdAt: string
  itemCount: number
  answeredCount: number
  wrongCount: number
  status: 'completed' | 'incomplete'
}

export type LearningEvaluation = {
  resources: Array<EvaluationResource>
  wrongRecords: Array<{
    id: string
    itemType: string
    itemId: string
    topic: string
    userAnswer?: string | null
    correctAnswer: string
    createdAt: string
  }>
}

export const learningEvaluationAtom = Atom.family((projectId: string) =>
  Atom.make(
    Effect.gen(function* () {
      const { apiClient } = yield* ApiClientService
      const [quizzes, flashcardGroups, records] = yield* Effect.all(
        [
          apiClient.listQuizzesApiV1ProjectsProjectIdQuizzesGet(projectId),
          apiClient.listFlashcardGroupsApiV1ProjectsProjectIdFlashcardGroupsGet(
            projectId,
          ),
          apiClient.listPracticeRecordsApiV1ProjectsProjectIdPracticeRecordsGet(
            projectId,
          ),
        ],
        { concurrency: 'unbounded' },
      )

      const quizResources = yield* Effect.all(
        quizzes.map((quiz) =>
          Effect.map(
            apiClient.listQuizQuestionsApiV1ProjectsProjectIdQuizzesQuizIdQuestionsGet(
              projectId,
              quiz.id,
            ),
            (questions): EvaluationResource => {
              const ids = new Set(questions.map((question) => question.id))
              const attempts = records.filter(
                (record) => record.item_type === 'quiz' && ids.has(record.item_id),
              )
              const answered = new Set(attempts.map((record) => record.item_id))
              return {
                id: quiz.id,
                type: 'quiz',
                name: quiz.name,
                description: quiz.description,
                createdAt: quiz.created_at,
                itemCount: questions.length,
                answeredCount: answered.size,
                wrongCount: attempts.filter((record) => !record.was_correct).length,
                status:
                  questions.length > 0 && answered.size >= questions.length
                    ? 'completed'
                    : 'incomplete',
              }
            },
          ),
        ),
        { concurrency: 'unbounded' },
      )

      const flashcardResources = yield* Effect.all(
        flashcardGroups.map((group) =>
          Effect.map(
            apiClient.listFlashcardsApiV1ProjectsProjectIdFlashcardGroupsGroupIdFlashcardsGet(
              projectId,
              group.id,
            ),
            (flashcards): EvaluationResource => {
              const ids = new Set(flashcards.map((flashcard) => flashcard.id))
              const attempts = records.filter(
                (record) =>
                  record.item_type === 'flashcard' && ids.has(record.item_id),
              )
              const answered = new Set(attempts.map((record) => record.item_id))
              return {
                id: group.id,
                type: 'flashcard',
                name: group.name,
                description: group.description,
                createdAt: group.created_at,
                itemCount: flashcards.length,
                answeredCount: answered.size,
                wrongCount: attempts.filter((record) => !record.was_correct).length,
                status:
                  flashcards.length > 0 && answered.size >= flashcards.length
                    ? 'completed'
                    : 'incomplete',
              }
            },
          ),
        ),
        { concurrency: 'unbounded' },
      )

      return {
        resources: [...quizResources, ...flashcardResources].sort((a, b) =>
          b.createdAt.localeCompare(a.createdAt),
        ),
        wrongRecords: records
          .filter((record) => !record.was_correct)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map((record) => ({
            id: record.id,
            itemType: record.item_type,
            itemId: record.item_id,
            topic: record.topic,
            userAnswer: record.user_answer,
            correctAnswer: record.correct_answer,
            createdAt: record.created_at,
          })),
      } satisfies LearningEvaluation
    }).pipe(Effect.provide(ApiClientService.Default)),
  ).pipe(Atom.keepAlive),
)
