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
  confidence: number
  trend: string
  status: string
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
