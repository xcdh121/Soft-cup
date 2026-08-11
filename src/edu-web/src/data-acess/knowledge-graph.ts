import { Atom } from '@effect-atom/atom-react'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer } from 'effect'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type KnowledgeGraphNode = {
  id: string
  label: string
  chapter_id: string | null
  difficulty_level: string
  position: number
  tags: Array<string>
  mastery_score: number
  mastery_probability: number
  p_correct_next: number
  confidence: number
  evidence_confidence: number
  trend: string
  status: string
  algorithm: string
  model_version: string
}

export type KnowledgeGraphEdge = {
  id: string
  source: string
  target: string
  relation_type: string
  strength: number
  description: string | null
}

export type KnowledgeGraph = {
  project_id: string
  course_id: string
  nodes: Array<KnowledgeGraphNode>
  edges: Array<KnowledgeGraphEdge>
}

export type KnowledgeStateEvent = {
  id: string
  event_type: string
  source_type: string
  source_id: string
  score_before: number
  score_after: number
  impact: number
  algorithm: string
  parameter_set_id: string | null
  prior_mastery: number | null
  prior_after_forgetting: number | null
  posterior_after_observation: number | null
  posterior_after_learning: number | null
  p_correct_before: number | null
  p_correct_next: number | null
  observed_score: number | null
  event_weight: number
  effective_parameters: Partial<Record<string, number>>
  reason_codes: Array<string>
  explanation_summary: string | null
  model_version: string
  occurred_at: string
}

const isSuccessStatus = (status: number) => status >= 200 && status < 300

export const knowledgeGraphAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      Effect.gen(function* () {
        const { httpClient } = yield* ApiClientService
        const path = `/api/v1/projects/${projectId}/knowledge-graph`
        const response = yield* httpClient.get(path)
        if (!isSuccessStatus(response.status)) {
          return yield* Effect.fail(
            new Error(`Request ${path} failed with status ${response.status}`),
          )
        }
        return (yield* response.json) as KnowledgeGraph
      }),
    )
    .pipe(Atom.keepAlive),
)

export const knowledgeStateEventsAtom = Atom.family((key: string) =>
  runtime
    .atom(
      key.length === 0
        ? Effect.succeed([] as Array<KnowledgeStateEvent>)
        : Effect.gen(function* () {
            const [projectId, knowledgePointId] = JSON.parse(key) as [
              string,
              string,
            ]
            const { httpClient } = yield* ApiClientService
            const path = `/api/v1/projects/${encodeURIComponent(projectId)}/knowledge-states/${encodeURIComponent(knowledgePointId)}/events?limit=5`
            const response = yield* httpClient.get(path)
            if (!isSuccessStatus(response.status)) {
              return yield* Effect.fail(
                new Error(
                  `Request ${path} failed with status ${response.status}`,
                ),
              )
            }
            return (yield* response.json) as Array<KnowledgeStateEvent>
          }),
    )
    .pipe(Atom.keepAlive),
)
