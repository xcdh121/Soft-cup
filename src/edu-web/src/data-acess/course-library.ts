import { Atom } from '@effect-atom/atom-react'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer } from 'effect'
import type { ProjectDto } from '@/integrations/api/client'
import type { ResourcePackage } from '@/data-acess/resource-package'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type Course = {
  id: string
  owner_id: string
  code: string | null
  name: string
  description: string | null
  status: string
  cover_url: string | null
  created_at: string
  updated_at: string
}

export type CourseChapter = {
  id: string
  course_id: string
  parent_chapter_id: string | null
  title: string
  description: string | null
  position: number
  learning_objectives: Array<string>
  estimated_minutes: number | null
  created_at: string
  updated_at: string
}

export type KnowledgePoint = {
  id: string
  course_id: string
  chapter_id: string | null
  name: string
  description: string | null
  difficulty_level: string
  position: number
  tags: Array<string>
  created_at: string
  updated_at: string
}

export type CourseResource = {
  id: string
  course_id: string
  chapter_id: string | null
  document_id: string | null
  document_project_id: string | null
  generated_resource_id: string | null
  resource_type: string
  title: string
  description: string | null
  source_type: string
  source_url: string | null
  difficulty_level: string
  estimated_minutes: number | null
  license_info: string | null
  target_audiences: Array<string>
  metadata: Record<string, unknown>
  knowledge_point_ids: Array<string>
  created_at: string
  updated_at: string
}

export type CourseQuestionLink = {
  id: string
  projectId: string
  projectName: string
  resourceId: string
  resourceName: string
  type: 'quiz' | 'programming_questions'
  title: string
  knowledgePointIds: Array<string>
}

export type ProjectCourseOutline = {
  courseId: string | null
  chapters: Array<CourseChapter>
  knowledgePoints: Array<KnowledgePoint>
}

const isSuccessStatus = (status: number) => status >= 200 && status < 300

const getJson = <T>(path: string) =>
  Effect.gen(function* () {
    const { httpClient } = yield* ApiClientService
    const response = yield* httpClient.get(path)
    if (!isSuccessStatus(response.status)) {
      return yield* Effect.fail(
        new Error(`Request ${path} failed with status ${response.status}`),
      )
    }
    return (yield* response.json) as T
  })

export const coursesAtom = runtime
  .atom(getJson<Array<Course>>('/api/v1/courses'))
  .pipe(Atom.keepAlive)

export const projectCourseOutlineAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      Effect.gen(function* () {
        if (!projectId) {
          return {
            courseId: null,
            chapters: [],
            knowledgePoints: [],
          } satisfies ProjectCourseOutline
        }

        const project = yield* getJson<ProjectDto>(
          `/api/v1/projects/${projectId}`,
        )
        if (!project.course_id) {
          return {
            courseId: null,
            chapters: [],
            knowledgePoints: [],
          } satisfies ProjectCourseOutline
        }

        const [chapters, knowledgePoints] = yield* Effect.all([
          getJson<Array<CourseChapter>>(
            `/api/v1/courses/${project.course_id}/chapters`,
          ),
          getJson<Array<KnowledgePoint>>(
            `/api/v1/courses/${project.course_id}/knowledge-points`,
          ),
        ])

        return {
          courseId: project.course_id,
          chapters,
          knowledgePoints,
        } satisfies ProjectCourseOutline
      }),
    )
    .pipe(Atom.keepAlive),
)

export const courseChaptersAtom = Atom.family((courseId: string) =>
  runtime
    .atom(getJson<Array<CourseChapter>>(`/api/v1/courses/${courseId}/chapters`))
    .pipe(Atom.keepAlive),
)

export const courseKnowledgePointsAtom = Atom.family((courseId: string) =>
  runtime
    .atom(
      getJson<Array<KnowledgePoint>>(
        `/api/v1/courses/${courseId}/knowledge-points`,
      ),
    )
    .pipe(Atom.keepAlive),
)

export const courseResourcesAtom = Atom.family((courseId: string) =>
  runtime
    .atom(
      getJson<Array<CourseResource>>(`/api/v1/courses/${courseId}/resources`),
    )
    .pipe(Atom.keepAlive),
)

export const courseQuestionsAtom = Atom.family((courseId: string) =>
  runtime
    .atom(
      Effect.gen(function* () {
        const { apiClient } = yield* ApiClientService
        const projects =
          (yield* apiClient.listProjectsApiV1ProjectsGet()).filter(
            (project) => project.course_id === courseId,
          )

        const questionsByProject = yield* Effect.all(
          projects.map((project) =>
            Effect.gen(function* () {
              const [quizzes, resourcePackages] = yield* Effect.all([
                apiClient.listQuizzesApiV1ProjectsProjectIdQuizzesGet(
                  project.id,
                ),
                getJson<Array<ResourcePackage>>(
                  `/api/v1/projects/${project.id}/resource-packages`,
                ),
              ])
              const quizQuestions = yield* Effect.all(
                quizzes.map((quiz) =>
                  Effect.map(
                    apiClient.listQuizQuestionsApiV1ProjectsProjectIdQuizzesQuizIdQuestionsGet(
                      project.id,
                      quiz.id,
                    ),
                    (questions) =>
                      questions.map(
                        (question): CourseQuestionLink => ({
                          id: question.id,
                          projectId: project.id,
                          projectName: project.name,
                          resourceId: quiz.id,
                          resourceName: quiz.name,
                          type: 'quiz',
                          title: question.question_text,
                          knowledgePointIds: question.knowledge_point_id
                            ? [question.knowledge_point_id]
                            : [],
                        }),
                      ),
                  ),
                ),
                { concurrency: 'unbounded' },
              )
              const programmingQuestions = resourcePackages.flatMap(
                (resourcePackage) =>
                  resourcePackage.resources.flatMap((resource) => {
                    if (
                      resource.resource_type !== 'programming_questions' ||
                      resource.status !== 'completed' ||
                      !Array.isArray(resource.content_json?.questions)
                    ) {
                      return []
                    }

                    return resource.content_json.questions.flatMap(
                      (question, index): Array<CourseQuestionLink> => {
                        if (!question || typeof question !== 'object') return []
                        const candidate = question as Record<string, unknown>
                        if (typeof candidate.title !== 'string') return []

                        return [
                          {
                            id: String(candidate.id ?? `q${index + 1}`),
                            projectId: project.id,
                            projectName: project.name,
                            resourceId: resource.id,
                            resourceName: resource.title,
                            type: 'programming_questions',
                            title: candidate.title,
                            knowledgePointIds: resource.knowledge_point_ids,
                          },
                        ]
                      },
                    )
                  }),
              )

              return [...quizQuestions.flat(), ...programmingQuestions]
            }),
          ),
          { concurrency: 'unbounded' },
        )

        return questionsByProject.flat()
      }),
    )
    .pipe(Atom.keepAlive),
)

export const knowledgePointResourcesAtom = Atom.family(
  (knowledgePointId: string) =>
    runtime
      .atom(
        getJson<Array<CourseResource>>(
          `/api/v1/knowledge-points/${knowledgePointId}/resources`,
        ),
      )
      .pipe(Atom.keepAlive),
)
