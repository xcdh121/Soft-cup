import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { withToast } from '@/lib/with-toast'
import { Atom, Registry } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer, Schema } from 'effect'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

type LearningPathStep = {
  step_no?: number
  type?: string
  target_id?: string | null
  title?: string
  reason?: string
}

type LearningPathContent = {
  title?: string
  estimated_minutes?: number
  path_steps?: Array<LearningPathStep>
  based_on_profile_fields?: Array<string>
  based_on_knowledge_points?: Array<string>
  adjust_reasons?: Array<string>
}

type LearningPathResponse = {
  path_id: string
  run_id: string
  project_id: string
  learning_path: LearningPathContent
  based_on_diagnosis_id?: string | null
  based_on_recommendation_ids: Array<string>
  created_at: string
}

type AgentEvent = {
  event_type: string
  agent_name?: string | null
  payload?: Record<string, unknown>
}

type AdaptedStudyPlan = {
  id: string
  user_id: string
  project_id: string
  content: {
    analysis: string
    focus_areas: Array<string>
    action_items: Array<{
      id: string
      parent_id: string | null
      type: 'quiz' | 'flashcard'
      title: string
      description: string | null
      source_type?: string
      is_navigable?: boolean
    }>
    schedule: Array<{
      day: string
      tasks: Array<string>
    }>
    encouragement: string
  }
  weak_topics: Array<string>
  created_at: string
  learning_path_id: string
  run_id: string
  planner_mode: 'llm' | 'rule_fallback' | 'rule' | 'unknown'
  raw_learning_path: LearningPathContent
}

const normalizeLabel = (value: string) =>
  value
    .replace(/^kp_/, '')
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')

const buildAnalysis = (path: LearningPathContent) => {
  const reasons = (path.adjust_reasons ?? []).filter(Boolean)
  const parts = [path.title, ...reasons].filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  )
  return parts.join(' ')
}

const buildFocusAreas = (path: LearningPathContent) => {
  return (path.based_on_knowledge_points ?? [])
    .filter(Boolean)
    .map(normalizeLabel)
    .slice(0, 5)
}

const inferActionType = (
  stepType: string | undefined,
): 'quiz' | 'flashcard' => {
  if (stepType === 'quiz') {
    return 'quiz'
  }
  if (stepType === 'practice') {
    return 'quiz'
  }
  return 'flashcard'
}

const buildActionItems = (path: LearningPathContent) =>
  (path.path_steps ?? []).map((step, index) => ({
    id: step.target_id || `path-step-${index + 1}`,
    parent_id: step.target_id || null,
    type: inferActionType(step.type),
    title: step.title || `Step ${index + 1}`,
    description: step.reason || null,
    source_type: step.type || 'resource',
    is_navigable:
      (step.type === 'quiz' || step.type === 'flashcard') && !!step.target_id,
  }))

const buildSchedule = (path: LearningPathContent) =>
  (path.path_steps ?? []).map((step, index) => ({
    day: `Day ${index + 1}`,
    tasks: [step.title, step.reason].filter(
      (value): value is string => typeof value === 'string' && value.length > 0,
    ),
  }))

const getPlannerModeFromEvents = (
  events: Array<AgentEvent>,
): AdaptedStudyPlan['planner_mode'] => {
  const plannerStep = [...events]
    .reverse()
    .find(
      (event) =>
        event.event_type === 'agent_step' &&
        event.agent_name === 'PlannerAgent',
    )

  const reasonCodes = Array.isArray(plannerStep?.payload?.reason_codes)
    ? plannerStep.payload.reason_codes
    : []

  if (reasonCodes.includes('llm')) {
    return 'llm'
  }
  if (reasonCodes.includes('rule_fallback')) {
    return 'rule_fallback'
  }
  if (reasonCodes.includes('rule')) {
    return 'rule'
  }
  return 'unknown'
}

const mapLearningPathToStudyPlan = (
  response: LearningPathResponse,
  plannerMode: AdaptedStudyPlan['planner_mode'] = 'unknown',
): AdaptedStudyPlan => {
  const path = response.learning_path ?? {}
  const focusAreas = buildFocusAreas(path)

  return {
    id: response.path_id,
    user_id: '',
    project_id: response.project_id,
    content: {
      analysis: buildAnalysis(path),
      focus_areas: focusAreas,
      action_items: buildActionItems(path),
      schedule: buildSchedule(path),
      encouragement:
        'Follow the path step by step, strengthen weak points first, then verify improvement with practice.',
    },
    weak_topics: focusAreas,
    created_at: response.created_at,
    learning_path_id: response.path_id,
    run_id: response.run_id,
    planner_mode: plannerMode,
    raw_learning_path: response.learning_path,
  }
}

const fetchJson = <T>(path: string) =>
  Effect.gen(function* () {
    const { httpClient } = yield* ApiClientService
    const response = yield* httpClient.get(path)
    return (yield* response.json) as T
  })

const fetchPlannerMode = (
  projectId: string,
  diagnosisId: string | null | undefined,
) =>
  Effect.gen(function* () {
    if (!diagnosisId) {
      return 'unknown' as const
    }

    const events = yield* fetchJson<Array<AgentEvent>>(
      `/api/v1/projects/${projectId}/diagnosis/${diagnosisId}/trace`,
    )
    return getPlannerModeFromEvents(events)
  })

export const latestStudyPlanRemoteAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      fetchJson<LearningPathResponse | null>(
        `/api/v1/projects/${projectId}/learning-paths/latest`,
      ).pipe(
        Effect.flatMap((response) =>
          response
            ? fetchPlannerMode(projectId, response.based_on_diagnosis_id).pipe(
                Effect.map((plannerMode) =>
                  mapLearningPathToStudyPlan(response, plannerMode),
                ),
              )
            : Effect.succeed(null),
        ),
      ),
    )
    .pipe(Atom.keepAlive),
)

export const studyPlansHistoryRemoteAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      fetchJson<Array<LearningPathResponse>>(
        `/api/v1/projects/${projectId}/learning-paths`,
      ).pipe(
        Effect.flatMap((responses) =>
          Effect.forEach(
            responses,
            (response) =>
              fetchPlannerMode(projectId, response.based_on_diagnosis_id).pipe(
                Effect.map((plannerMode) =>
                  mapLearningPathToStudyPlan(response, plannerMode),
                ),
              ),
            { concurrency: 4 },
          ),
        ),
      ),
    )
    .pipe(Atom.keepAlive),
)

export class StudyResource extends Schema.Class<StudyResource>('StudyResource')(
  {
    id: Schema.String,
    parent_id: Schema.NullOr(Schema.String),
    type: Schema.Literal('quiz', 'flashcard'),
    title: Schema.String,
    description: Schema.NullOr(Schema.String),
    source_type: Schema.optional(Schema.String),
    is_navigable: Schema.optional(Schema.Boolean),
  },
) {}

export const generateStudyPlanAtom = runtime.fn(
  Effect.fn(
    function* (projectId: string) {
      const registry = yield* Registry.AtomRegistry
      const { httpClient } = yield* ApiClientService

      const body = HttpBody.unsafeJson({
        trigger: {
          type: 'manual',
          id: 'study_plan_page',
        },
      })

      const response = yield* httpClient.post(
        `/api/v1/projects/${projectId}/learning-paths/generate`,
        { body },
      )

      const learningPath = (yield* response.json) as LearningPathResponse

      registry.refresh(latestStudyPlanRemoteAtom(projectId))
      registry.refresh(studyPlansHistoryRemoteAtom(projectId))

      return learningPath
    },
    withToast({
      onWaiting: '正在生成个性化学习计划...',
      onSuccess: '学习计划生成成功。',
      onFailure: '学习计划生成失败，请稍后重试。',
    }),
  ),
)
