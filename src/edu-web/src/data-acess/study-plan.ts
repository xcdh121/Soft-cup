import { Atom, Registry } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer, Schema, Stream } from 'effect'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { appendSseChunk } from '@/lib/sse'
import { withToast } from '@/lib/with-toast'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type LearningPathStep = {
  id?: string
  step_no?: number
  type?: string
  target_id?: string | null
  title?: string
  reason?: string
  objective?: string
  recommendation_id?: string | null
  knowledge_point_id?: string | null
  baseline_mastery?: number | null
  target_mastery?: number | null
  status?: string
  acceptance_condition?: Record<string, unknown> | string
}

export type LearningPathContent = {
  title?: string
  estimated_minutes?: number
  path_steps?: Array<LearningPathStep>
  based_on_profile_fields?: Array<string>
  based_on_knowledge_points?: Array<string>
  adjust_reasons?: Array<string>
  version?: number
  previous_path_id?: string | null
  status?: string
  adjust_trigger_type?: string | null
  adjust_trigger_id?: string | null
  adjust_trigger_ids?: Array<string>
  explanation_id?: string | null
  adjustment?: {
    trigger_type?: string
    trigger_id?: string
    trigger_ids?: Array<string>
    outcome_count?: number
    knowledge_point_count?: number
    target_achieved_count?: number
    needs_reinforcement_count?: number
    results?: Array<{
      outcome_id: string
      recommendation_id: string
      knowledge_point_id: string
      mastery_before: number
      mastery_after: number
      target_mastery: number
      target_achieved: boolean
      evaluated_at: string
    }>
    mastery_before?: number
    mastery_after?: number
    target_mastery?: number
    target_achieved?: boolean
  }
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

const StudyPlanProgressUpdate = Schema.Struct({
  event: Schema.String,
  status: Schema.String,
  message: Schema.NullishOr(Schema.String),
  summary: Schema.NullishOr(Schema.String),
  agent_name: Schema.NullishOr(Schema.String),
  event_type: Schema.NullishOr(Schema.String),
  payload: Schema.NullishOr(Schema.Unknown),
  result: Schema.NullishOr(Schema.Unknown),
  error: Schema.NullishOr(Schema.String),
})

type StudyPlanProgress = {
  event: string
  status: string
  message: string
  agentName?: string
  eventType?: string
  partialPlan?: LearningPathContent
  recommendations?: Array<StudyPlanRecommendationPreview>
  error?: string
}

export type StudyPlanRecommendationPreview = {
  id: string
  title: string
  recommendation_type?: string
  reason_text: Array<string>
}

const partialLearningPathFromPayload = (
  payload: unknown,
): LearningPathContent | undefined => {
  if (!payload || typeof payload !== 'object') return undefined
  const value = payload as Record<string, unknown>
  if (value.partial !== true) return undefined
  if (!value.learning_path || typeof value.learning_path !== 'object') {
    return undefined
  }
  return value.learning_path
}

const recommendationsFromPayload = (
  payload: unknown,
): Array<StudyPlanRecommendationPreview> | undefined => {
  if (!payload || typeof payload !== 'object') return undefined
  const value = payload as Record<string, unknown>
  if (!Array.isArray(value.recommendations)) return undefined
  return value.recommendations
    .filter(
      (item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === 'object',
    )
    .map((item, index) => ({
      id:
        typeof item.id === 'string'
          ? item.id
          : `recommendation-preview-${index}`,
      title: typeof item.title === 'string' ? item.title : '学习推荐',
      recommendation_type:
        typeof item.recommendation_type === 'string'
          ? item.recommendation_type
          : undefined,
      reason_text: Array.isArray(item.reason_text)
        ? item.reason_text.filter(
            (reason): reason is string => typeof reason === 'string',
          )
        : [],
    }))
}

const progressMessage = (
  progress: typeof StudyPlanProgressUpdate.Type,
): string => {
  if (progress.event === 'completed') return '学习计划生成完成。'
  if (progress.event === 'failed') return progress.error || '学习计划生成失败。'

  if (progress.status === 'running') {
    const agentMessages: Record<string, string> = {
      ProfileAgent: '正在分析学习画像…',
      KTAgent: '正在评估知识点掌握情况…',
      CollectiveInsightAgent: '正在汇总学习表现…',
      DiagnosisAgent: '正在诊断薄弱知识点…',
      ResourceAgent: '正在匹配学习资源…',
      PlannerAgent: '正在生成个性化学习路径…',
      SupervisorAgent: '正在准备学习计划…',
    }
    if (progress.agent_name && agentMessages[progress.agent_name]) {
      return agentMessages[progress.agent_name]
    }
  }

  if (progress.event_type === 'route_decided') return '分析流程已确定。'
  if (progress.event_type === 'artifact_updated') return '已完成一个分析阶段。'
  return progress.message || progress.summary || '正在生成学习计划…'
}

export const studyPlanProgressAtom = Atom.make<StudyPlanProgress | null>(null)

export type AdaptedStudyPlan = {
  id: string
  user_id: string
  project_id: string
  content: {
    analysis: string
    focus_areas: Array<string>
    action_items: Array<{
      id: string
      parent_id: string | null
      recommendation_id?: string | null
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
  version: number
  previous_path_id: string | null
  status: string
  based_on_recommendation_ids: Array<string>
  based_on_diagnosis_id: string | null
  raw_learning_path: LearningPathContent
}

const normalizeLabel = (value: string) =>
  value
    .replace(/^kp_/, '')
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const legacyPlanText: Record<string, string> = {
  'Personalized reinforcement path': '个性化巩固学习路径',
  'Practice to verify improvement': '完成推荐后的巩固练习',
  'Use targeted practice to confirm the weak point is improving.':
    '通过针对性练习巩固当前薄弱知识点。',
  'Recommended next step.': '建议按此顺序完成学习资源。',
  'Prioritize the weakest knowledge points first.':
    '优先巩固当前掌握度最低的知识点。',
  'Sequence available recommendations into an actionable plan.':
    '把已生成的推荐资源组织为可执行的学习顺序。',
}

const studentFacingPlanText = (value: string | undefined, fallback: string) =>
  value ? (legacyPlanText[value.trim()] ?? value) : fallback

const buildAnalysis = (path: LearningPathContent) => {
  const reasons = (path.adjust_reasons ?? []).filter(Boolean)
  const parts = [path.title, ...reasons].filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  )
  return parts.join(' ')
}

const buildFocusAreas = (path: LearningPathContent) => {
  const labels = (path.based_on_knowledge_points ?? [])
    .filter((value) => value && !UUID_PATTERN.test(value))
    .map(normalizeLabel)
  return [...new Set(labels)].slice(0, 5)
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
    recommendation_id: step.recommendation_id ?? null,
    type: inferActionType(step.type),
    title: studentFacingPlanText(step.title, `学习步骤 ${index + 1}`),
    description: step.reason ? studentFacingPlanText(step.reason, '') : null,
    source_type: step.type || 'resource',
    is_navigable:
      (step.type === 'quiz' || step.type === 'flashcard') && !!step.target_id,
  }))

const completionGuide = (stepType: string | undefined) => {
  if (stepType === 'quiz' || stepType === 'practice') {
    return '核对练习结果，把错题对应的知识点、错误原因和正确思路分别记录下来。'
  }
  if (stepType === 'flashcard' || stepType === 'flashcards') {
    return '筛出仍需提示才能回忆的卡片，并在当天结束前进行一次无提示复述。'
  }
  if (stepType === 'mind_map') {
    return '补充概念之间的连接关系，并尝试不看资料复述完整知识结构。'
  }
  if (stepType === 'note') {
    return '整理一份自己的要点摘要，并写下至少一个仍需继续确认的问题。'
  }
  return '用自己的话总结核心内容，记录完成情况以及下一次复习时需要重点关注的问题。'
}

const scheduleTaskFromStep = (
  step: LearningPathStep,
  focus: string,
  isReview: boolean,
) => {
  const title = studentFacingPlanText(step.title, focus)
  const reason = step.reason
    ? studentFacingPlanText(step.reason, '')
    : `本次任务用于巩固当前计划中的「${focus}」。`
  const objective = step.objective
    ? studentFacingPlanText(step.objective, '')
    : `能够独立说明「${focus}」的关键概念并完成对应行动项。`
  const acceptance =
    typeof step.acceptance_condition === 'string'
      ? studentFacingPlanText(step.acceptance_condition, '')
      : completionGuide(step.type)

  return `${isReview ? '回顾并强化' : '完成'}「${title}」，本日重点围绕「${focus}」展开。学习原因：${reason} 学习目标：${objective} 完成后：${acceptance}`
}

export const buildWeeklySchedule = (path: LearningPathContent) => {
  const steps = (path.path_steps ?? []).filter((step) =>
    Boolean(step.title || step.reason || step.objective),
  )
  const knowledgePoints = (path.based_on_knowledge_points ?? [])
    .filter((value) => value && !UUID_PATTERN.test(value))
    .map(normalizeLabel)
  const planFocus = studentFacingPlanText(path.title, '本周重点知识')
  const focusFor = (index: number, step?: LearningPathStep) =>
    (knowledgePoints.length > 0
      ? knowledgePoints[index % knowledgePoints.length]
      : undefined) || studentFacingPlanText(step?.title, planFocus)

  const schedule = Array.from({ length: 7 }, (_, index) => {
    const step = steps.length > 0 ? steps[index % steps.length] : undefined
    const focus = focusFor(index, step)
    const task = step
      ? scheduleTaskFromStep(step, focus, index >= steps.length)
      : `围绕「${focus}」梳理本周学习目标，结合当前学习路径整理关键概念、已有证据与尚未解决的问题。完成后用自己的话形成一份学习摘要，并明确下一次学习需要验证的内容。`
    return { day: `第 ${index + 1} 天`, tasks: [task] }
  })

  steps.slice(7).forEach((step, index) => {
    const dayIndex = index % schedule.length
    schedule[dayIndex].tasks.push(
      scheduleTaskFromStep(step, focusFor(dayIndex, step), false),
    )
  })

  return schedule
}

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
  const path = response.learning_path
  const focusAreas = buildFocusAreas(path)

  return {
    id: response.path_id,
    user_id: '',
    project_id: response.project_id,
    content: {
      analysis: buildAnalysis(path),
      focus_areas: focusAreas,
      action_items: buildActionItems(path),
      schedule: buildWeeklySchedule(path),
      encouragement: '不积跬步，无以至千里',
    },
    weak_topics: focusAreas,
    created_at: response.created_at,
    learning_path_id: response.path_id,
    run_id: response.run_id,
    planner_mode: plannerMode,
    version: path.version ?? 1,
    previous_path_id: path.previous_path_id ?? null,
    status: path.status ?? 'active',
    based_on_recommendation_ids: response.based_on_recommendation_ids,
    based_on_diagnosis_id: response.based_on_diagnosis_id ?? null,
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
    recommendation_id: Schema.optional(Schema.NullOr(Schema.String)),
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

      registry.set(studyPlanProgressAtom, {
        event: 'started',
        status: 'running',
        message: '正在准备学习计划…',
        recommendations: [],
      })

      const body = HttpBody.unsafeJson({
        trigger: {
          type: 'manual',
          id: 'study_plan_page',
        },
      })

      const response = yield* httpClient.post(
        `/api/v1/projects/${projectId}/learning-paths/generate/stream`,
        { body },
      )

      let learningPath: LearningPathResponse | undefined
      let streamError: string | undefined
      let streamedLearningPath: LearningPathContent | undefined
      let streamedRecommendations: Array<StudyPlanRecommendationPreview> = []
      const decoder = new TextDecoder()
      let buffer = ''
      const responseStream = response.stream.pipe(
        Stream.map((value) => {
          const parsed = appendSseChunk(
            buffer,
            decoder.decode(value, { stream: true }),
          )
          buffer = parsed.buffer
          return parsed.blocks
        }),
        Stream.flatMap((blocks) => Stream.fromIterable(blocks)),
        Stream.map((block) =>
          block
            .split('\n')
            .map((line) => (line.startsWith('data: ') ? line.slice(6) : ''))
            .filter(Boolean)
            .join('\n'),
        ),
        Stream.filter(Boolean),
        Stream.flatMap((chunk) =>
          Schema.decodeUnknown(Schema.parseJson(StudyPlanProgressUpdate))(
            chunk,
          ),
        ),
        Stream.tap((progress) =>
          Effect.sync(() => {
            if (progress.result) {
              learningPath = progress.result as LearningPathResponse
              streamedLearningPath = learningPath.learning_path
            }
            streamedLearningPath =
              partialLearningPathFromPayload(progress.payload) ??
              streamedLearningPath
            streamedRecommendations =
              recommendationsFromPayload(progress.payload) ??
              streamedRecommendations
            if (progress.error) {
              streamError = progress.error
            }
            registry.set(studyPlanProgressAtom, {
              event: progress.event,
              status: progress.status,
              message: progressMessage(progress),
              agentName: progress.agent_name ?? undefined,
              eventType: progress.event_type ?? undefined,
              partialPlan: streamedLearningPath,
              recommendations: streamedRecommendations,
              error: progress.error ?? undefined,
            })
          }),
        ),
      )

      yield* Stream.runCollect(responseStream)

      if (streamError) {
        throw new Error(streamError)
      }
      if (!learningPath) {
        throw new Error('学习计划生成结束，但没有返回计划内容。')
      }

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
