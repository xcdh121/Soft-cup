import { Atom, Registry } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer } from 'effect'
import {
  latestStudyPlanRemoteAtom,
  studyPlansHistoryRemoteAtom,
} from './study-plan'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type RecommendationEventType =
  | 'impression'
  | 'clicked'
  | 'started'
  | 'progressed'
  | 'completed'
  | 'dismissed'
  | 'skipped'
  | 'rated'

export type LearningRecommendation = {
  id: string
  recommendation_type: string
  target_id: string | null
  title: string
  reason_codes: Array<string>
  reason_text: Array<string>
  score: number | null
  expected_outcome: Record<string, unknown>
  verification_plan: Record<string, unknown>
  status: string
  valid_until: string | null
}

export type RecommendationInteraction = {
  id: string
  recommendation_id: string
  event_type: RecommendationEventType
  resource_id: string | null
  learning_session_id: string | null
  progress: number | null
  duration_ms: number | null
  rating: number | null
  reason_code: string | null
  occurred_at: string
  metadata: Record<string, unknown>
}

export type InterventionOutcome = {
  id: string
  recommendation_id: string
  knowledge_point_id: string
  baseline_state_event_id: string
  verification_event_id: string
  mastery_before: number
  mastery_after: number
  mastery_gain: number
  verification_score: number
  target_mastery: number
  target_achieved: boolean
  attribution_confidence: number
  evaluation_window_hours: number
  evaluated_at: string
  explanation_id: string | null
}

export type KTMetricSummary = {
  event_count: number
  brier_score: number | null
  log_loss: number | null
  expected_calibration_error: number | null
  legacy_brier_score: number | null
  legacy_log_loss: number | null
  legacy_expected_calibration_error: number | null
  brier_score_improvement: number | null
  log_loss_improvement: number | null
  mapping_coverage: number
  low_evidence_ratio: number
}

export type KTParameterSet = {
  id: string
  name: string
  version: string
  scope_type: string
  scope_id: string | null
  initial_mastery: number
  learn_probability: number
  slip_probability: number
  guess_probability: number
  forget_probability_daily: number
  difficulty_adjustments: Record<string, unknown>
  answer_mode_adjustments: Record<string, unknown>
  status: string
  expert_reason: string | null
  effective_from: string | null
  created_by: string | null
  created_at: string
}

export type ClosedLoopOverview = {
  recommendations: Array<LearningRecommendation>
  interactionsByRecommendation: Record<string, Array<RecommendationInteraction>>
  outcomes: Array<InterventionOutcome>
}

export type DiagnosisOverview = {
  diagnosis_id: string
  diagnosis: {
    summary?: string
    root_causes?: Array<{
      type?: string
      knowledge_point_id?: string
      confidence?: number
      reason_text?: string
      relation_id?: string | null
    }>
    evidences?: Array<{
      source_type?: string
      source_id?: string
      knowledge_point_id?: string
      contribution_score?: number
    }>
  }
}

const isSuccessStatus = (status: number) => status >= 200 && status < 300

const requestJson = <T>(
  method: 'get' | 'post' | 'put',
  path: string,
  body?: unknown,
) =>
  Effect.gen(function* () {
    const { httpClient } = yield* ApiClientService
    const options =
      body === undefined ? undefined : { body: HttpBody.unsafeJson(body) }
    const response =
      method === 'get'
        ? yield* httpClient.get(path)
        : method === 'post'
          ? yield* httpClient.post(path, options)
          : yield* httpClient.put(path, options)
    if (!isSuccessStatus(response.status)) {
      return yield* Effect.fail(
        new Error(`请求失败（${response.status}）：${path}`),
      )
    }
    return (yield* response.json) as T
  })

export const closedLoopOverviewAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      Effect.gen(function* () {
        const [recommendations, outcomes] = yield* Effect.all(
          [
            requestJson<Array<LearningRecommendation>>(
              'get',
              `/api/v1/projects/${projectId}/recommendations`,
            ),
            requestJson<Array<InterventionOutcome>>(
              'get',
              `/api/v1/projects/${projectId}/intervention-outcomes`,
            ),
          ],
          { concurrency: 2 },
        )
        const interactionEntries = yield* Effect.forEach(
          recommendations,
          (recommendation) =>
            requestJson<Array<RecommendationInteraction>>(
              'get',
              `/api/v1/projects/${projectId}/recommendations/${recommendation.id}/interactions`,
            ).pipe(
              Effect.map(
                (interactions) => [recommendation.id, interactions] as const,
              ),
            ),
          { concurrency: 4 },
        )
        return {
          recommendations,
          interactionsByRecommendation: Object.fromEntries(interactionEntries),
          outcomes,
        } satisfies ClosedLoopOverview
      }),
    )
    .pipe(Atom.keepAlive),
)

export const diagnosisOverviewAtom = Atom.family((key: string) =>
  runtime
    .atom(
      key.length === 0
        ? Effect.succeed(null as DiagnosisOverview | null)
        : Effect.gen(function* () {
            const [projectId, diagnosisId] = JSON.parse(key) as [string, string]
            return yield* requestJson<DiagnosisOverview>(
              'get',
              `/api/v1/projects/${projectId}/diagnosis/${diagnosisId}`,
            )
          }),
    )
    .pipe(Atom.keepAlive),
)

export const refreshClosedLoopOverviewAtom = runtime.fn(
  Effect.fn(function* (projectId: string) {
    const registry = yield* Registry.AtomRegistry
    registry.refresh(closedLoopOverviewAtom(projectId))
  }),
)

export const recordRecommendationFeedbackAtom = runtime.fn(
  Effect.fn(function* (input: {
    projectId: string
    recommendationId: string
    eventType: RecommendationEventType
    resourceId?: string
    progress?: number
    durationMs?: number
    rating?: number
    reasonCode?: string
    metadata?: Record<string, unknown>
  }) {
    const registry = yield* Registry.AtomRegistry
    const result = yield* requestJson<RecommendationInteraction>(
      'post',
      `/api/v1/projects/${input.projectId}/recommendations/${input.recommendationId}/feedback`,
      {
        event_type: input.eventType,
        resource_id: input.resourceId,
        progress: input.progress,
        duration_ms: input.durationMs,
        rating: input.rating,
        reason_code: input.reasonCode,
        metadata: input.metadata ?? {},
      },
    )
    registry.refresh(closedLoopOverviewAtom(input.projectId))
    registry.refresh(latestStudyPlanRemoteAtom(input.projectId))
    registry.refresh(studyPlansHistoryRemoteAtom(input.projectId))
    return result
  }),
)

export const adjustLearningPathAtom = runtime.fn(
  Effect.fn(function* (input: {
    projectId: string
    pathId: string
    outcomeIds: Array<string>
  }) {
    const registry = yield* Registry.AtomRegistry
    const result = yield* requestJson<Record<string, unknown>>(
      'post',
      `/api/v1/projects/${input.projectId}/learning-paths/${input.pathId}/adjust`,
      {
        trigger_type: 'intervention_outcomes',
        outcome_ids: input.outcomeIds,
      },
    )
    registry.refresh(closedLoopOverviewAtom(input.projectId))
    registry.refresh(latestStudyPlanRemoteAtom(input.projectId))
    registry.refresh(studyPlansHistoryRemoteAtom(input.projectId))
    return result
  }),
)

export const ktMetricSummaryAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      requestJson<KTMetricSummary>(
        'get',
        `/api/v1/projects/${projectId}/knowledge-states/metrics/summary`,
      ),
    )
    .pipe(Atom.keepAlive),
)

export const ktParameterSetsAtom = runtime
  .atom(requestJson<Array<KTParameterSet>>('get', '/api/v1/kt/parameter-sets'))
  .pipe(Atom.keepAlive)

export const createKTParameterSetAtom = runtime.fn(
  Effect.fn(function* (input: {
    name: string
    version: string
    scopeType: string
    scopeId?: string
    initialMastery: number
    learnProbability: number
    slipProbability: number
    guessProbability: number
    forgetProbabilityDaily: number
    expertReason?: string
  }) {
    const registry = yield* Registry.AtomRegistry
    const result = yield* requestJson<KTParameterSet>(
      'post',
      '/api/v1/kt/parameter-sets',
      {
        name: input.name,
        version: input.version,
        scope_type: input.scopeType,
        scope_id: input.scopeId || null,
        initial_mastery: input.initialMastery,
        learn_probability: input.learnProbability,
        slip_probability: input.slipProbability,
        guess_probability: input.guessProbability,
        forget_probability_daily: input.forgetProbabilityDaily,
        difficulty_adjustments: {},
        answer_mode_adjustments: {},
        status: 'draft',
        expert_reason: input.expertReason || null,
      },
    )
    registry.refresh(ktParameterSetsAtom)
    return result
  }),
)

export const activateKTParameterSetAtom = runtime.fn(
  Effect.fn(function* (parameterSetId: string) {
    const registry = yield* Registry.AtomRegistry
    const result = yield* requestJson<KTParameterSet>(
      'post',
      `/api/v1/kt/parameter-sets/${parameterSetId}/activate`,
    )
    registry.refresh(ktParameterSetsAtom)
    return result
  }),
)

export const setKnowledgePointKTOverrideAtom = runtime.fn(
  Effect.fn(function* (input: {
    knowledgePointId: string
    parameterSetId: string
    initialMastery?: number
    learnProbability?: number
    slipProbability?: number
    guessProbability?: number
    forgetProbabilityDaily?: number
    expertReason?: string
  }) {
    return yield* requestJson<Record<string, unknown>>(
      'put',
      `/api/v1/kt/knowledge-points/${input.knowledgePointId}/parameters`,
      {
        parameter_set_id: input.parameterSetId,
        initial_mastery_override: input.initialMastery,
        learn_override: input.learnProbability,
        slip_override: input.slipProbability,
        guess_override: input.guessProbability,
        forget_override: input.forgetProbabilityDaily,
        expert_reason: input.expertReason || null,
      },
    )
  }),
)
