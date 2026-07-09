import { Atom } from '@effect-atom/atom-react'
import { Effect } from 'effect'
import { ApiClientService } from '@/integrations/api/http'
import type { ResourcePackage } from '@/data-acess/resource-package'

export type ProgrammingQuestion = {
  id: string
  title: string
  description: string
  inputFormat?: string
  outputFormat?: string
  constraints: Array<string>
  examples: Array<{
    input: string
    output: string
    explanation?: string
  }>
  starterCode?: string
  referenceSolution?: string
  hints: Array<string>
  difficulty?: string
}

export type EvaluationResource = {
  id: string
  type: 'quiz' | 'flashcard' | 'programming_questions'
  name: string
  description?: string | null
  createdAt: string
  itemCount: number
  answeredCount: number
  wrongCount: number
  status: 'completed' | 'incomplete'
  resourcePackageId?: string
  programmingQuestions?: Array<ProgrammingQuestion>
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
      const { apiClient, httpClient } = yield* ApiClientService
      const [quizzes, flashcardGroups, records, resourcePackages] = yield* Effect.all(
        [
          apiClient.listQuizzesApiV1ProjectsProjectIdQuizzesGet(projectId),
          apiClient.listFlashcardGroupsApiV1ProjectsProjectIdFlashcardGroupsGet(
            projectId,
          ),
          apiClient.listPracticeRecordsApiV1ProjectsProjectIdPracticeRecordsGet(
            projectId,
          ),
          Effect.gen(function* () {
            const response = yield* httpClient.get(
              `/api/v1/projects/${projectId}/resource-packages`,
            )
            return (yield* response.json) as Array<ResourcePackage>
          }),
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

      const programmingResources: Array<EvaluationResource> =
        resourcePackages.flatMap((resourcePackage) =>
          resourcePackage.resources
            .filter(
              (resource) =>
                resource.resource_type === 'programming_questions' &&
                resource.status === 'completed',
            )
            .flatMap((resource) => {
              const questions = parseProgrammingQuestions(resource.content_json)
              if (questions.length === 0) return []
              return [{
                id: resource.id,
                type: 'programming_questions' as const,
                name: resource.title,
                description: resource.summary,
                createdAt: resource.created_at,
                itemCount: questions.length,
                answeredCount: 0,
                wrongCount: 0,
                status: 'incomplete' as const,
                resourcePackageId: resourcePackage.id,
                programmingQuestions: questions,
              }]
            }),
        )

      return {
        resources: [
          ...quizResources,
          ...flashcardResources,
          ...programmingResources,
        ].sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
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

const parseStringList = (value: unknown): Array<string> =>
  Array.isArray(value) ? value.map(String).filter(Boolean) : []

const parseProgrammingQuestions = (
  content: Record<string, unknown> | null,
): Array<ProgrammingQuestion> => {
  const questions = content?.questions
  if (!Array.isArray(questions)) return []

  return questions.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const candidate = item as Record<string, unknown>
    const title = candidate.title
    const description = candidate.description
    if (typeof title !== 'string' || typeof description !== 'string') return []

    const examples = Array.isArray(candidate.examples)
      ? candidate.examples.flatMap((example) => {
          if (!example || typeof example !== 'object') return []
          const row = example as Record<string, unknown>
          return [{
            input: String(row.input ?? ''),
            output: String(row.output ?? ''),
            explanation:
              typeof row.explanation === 'string' ? row.explanation : undefined,
          }]
        })
      : []

    return [{
      id: String(candidate.id ?? `q${index + 1}`),
      title,
      description,
      inputFormat:
        typeof candidate.input_format === 'string'
          ? candidate.input_format
          : undefined,
      outputFormat:
        typeof candidate.output_format === 'string'
          ? candidate.output_format
          : undefined,
      constraints: parseStringList(candidate.constraints),
      examples,
      starterCode:
        typeof candidate.starter_code === 'string'
          ? candidate.starter_code
          : undefined,
      referenceSolution:
        typeof candidate.reference_solution === 'string'
          ? candidate.reference_solution
          : undefined,
      hints: parseStringList(candidate.hints),
      difficulty:
        typeof candidate.difficulty === 'string' ? candidate.difficulty : undefined,
    }]
  })
}
