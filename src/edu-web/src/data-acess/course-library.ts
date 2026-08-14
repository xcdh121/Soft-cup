import { Atom, Registry, Result } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer } from 'effect'
import type { ProjectDto } from '@/integrations/api/client'
import type {
  GeneratedResource,
  ResourcePackage,
} from '@/data-acess/resource-package'
import { authAtom } from '@/data-acess/auth'
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
  generated_resource: GeneratedResource | null
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
  questionCount: number
  knowledgePointIds: Array<string>
}

export const createCourseQuizQuestionGroup = (input: {
  quizId: string
  quizName: string
  projectId: string
  projectName: string
  questions: ReadonlyArray<{ knowledge_point_id?: string | null }>
}): CourseQuestionLink | null => {
  if (input.questions.length === 0) return null

  return {
    id: input.quizId,
    projectId: input.projectId,
    projectName: input.projectName,
    resourceId: input.quizId,
    resourceName: input.quizName,
    type: 'quiz',
    title: input.quizName,
    questionCount: input.questions.length,
    knowledgePointIds: Array.from(
      new Set(
        input.questions.flatMap((question) =>
          question.knowledge_point_id ? [question.knowledge_point_id] : [],
        ),
      ),
    ),
  }
}

export type ProjectCourseOutline = {
  courseId: string | null
  chapters: Array<CourseChapter>
  knowledgePoints: Array<KnowledgePoint>
}

export type AddGeneratedResourceToCourseInput = {
  courseId: string
  chapterId?: string | null
  knowledgePointIds: Array<string>
  resource: GeneratedResource
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

const coursesRemoteAtom = runtime.atom(
  getJson<Array<Course>>('/api/v1/courses'),
)

// Some globally mounted UI (for example dialogs and navigation helpers) can
// subscribe before the dashboard is visible. Keep the authenticated request
// behind the session atom so public routes never issue a guaranteed 401. Once
// a session appears this derived atom automatically starts the remote atom.
export const coursesAtom = Atom.make((get) => {
  const { session, user } = get(authAtom)
  return session && user
    ? get(coursesRemoteAtom)
    : Result.success<Array<Course>>([])
})

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

export const courseGeneratedResourcesAtom = Atom.family((courseId: string) =>
  runtime
    .atom(
      Effect.gen(function* () {
        const { apiClient } = yield* ApiClientService
        const projects =
          (yield* apiClient.listProjectsApiV1ProjectsGet()).filter(
            (project) => project.course_id === courseId,
          )
        const packagesByProject = yield* Effect.all(
          projects.map((project) =>
            getJson<Array<ResourcePackage>>(
              `/api/v1/projects/${project.id}/resource-packages`,
            ),
          ),
          { concurrency: 'unbounded' },
        )

        return packagesByProject
          .flatMap((resourcePackages) =>
            resourcePackages.flatMap(
              (resourcePackage) => resourcePackage.resources,
            ),
          )
          .filter((resource) => resource.status === 'completed')
      }),
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
              const quizQuestionGroups = yield* Effect.all(
                quizzes.map((quiz) =>
                  Effect.map(
                    apiClient.listQuizQuestionsApiV1ProjectsProjectIdQuizzesQuizIdQuestionsGet(
                      project.id,
                      quiz.id,
                    ),
                    (questions): Array<CourseQuestionLink> => {
                      const group = createCourseQuizQuestionGroup({
                        quizId: quiz.id,
                        quizName: quiz.name,
                        projectId: project.id,
                        projectName: project.name,
                        questions,
                      })
                      return group ? [group] : []
                    },
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

                    return [
                      {
                        id: resource.id,
                        projectId: project.id,
                        projectName: project.name,
                        resourceId: resource.id,
                        resourceName: resource.title,
                        type: 'programming_questions' as const,
                        title: resource.title,
                        questionCount: resource.content_json.questions.length,
                        knowledgePointIds: resource.knowledge_point_ids,
                      },
                    ]
                  }),
              )

              return [...quizQuestionGroups.flat(), ...programmingQuestions]
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

export const addGeneratedResourceToCourseAtom = runtime.fn(
  Effect.fn(function* (input: AddGeneratedResourceToCourseInput) {
    const registry = yield* Registry.AtomRegistry
    const { httpClient } = yield* ApiClientService
    const { resource } = input
    const response = yield* httpClient.post(
      `/api/v1/courses/${input.courseId}/resources`,
      {
        body: HttpBody.unsafeJson({
          chapter_id: input.chapterId ?? null,
          document_id: null,
          generated_resource_id: resource.id,
          resource_type: resource.resource_type,
          title: resource.title,
          description: resource.summary,
          source_type: 'generated',
          source_url: null,
          difficulty_level: resource.difficulty_level,
          estimated_minutes: resource.estimated_minutes,
          license_info: 'AI 生成内容，发布前请复核',
          target_audiences: [resource.difficulty_level],
          metadata: {
            project_id: resource.project_id,
            resource_package_id: resource.resource_package_id,
            generator_agent: resource.generator_agent,
            generation_reason: resource.generation_reason,
          },
          knowledge_point_ids: input.knowledgePointIds,
        }),
      },
    )
    if (!isSuccessStatus(response.status)) {
      return yield* Effect.fail(
        new Error(`加入课程失败（HTTP ${response.status}）`),
      )
    }
    const courseResource = (yield* response.json) as CourseResource
    registry.refresh(courseResourcesAtom(input.courseId))
    for (const knowledgePointId of input.knowledgePointIds) {
      registry.refresh(knowledgePointResourcesAtom(knowledgePointId))
    }
    return courseResource
  }),
)
