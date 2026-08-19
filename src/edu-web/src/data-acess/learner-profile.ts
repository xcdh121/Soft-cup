import { Atom, Registry } from '@effect-atom/atom-react'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer } from 'effect'
import { knowledgeGraphAtom } from './knowledge-graph'
import { practiceRecordsRemoteAtom } from './practice'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { withToast } from '@/lib/with-toast'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type LearnerProfileField = {
  value?: unknown
  confidence?: number
  status?: string
  evidence?: Array<Record<string, unknown>>
  updated_at?: string
}

export type LearnerProfile = {
  id: string
  user_id: string
  project_id: string
  status: string
  profile_data: Record<string, LearnerProfileField | unknown> | null
  completeness_score: number
  last_refreshed_at: string | null
  created_at: string
  updated_at: string
}

export type LearnerProfileRevision = {
  id: string
  profile_id: string
  field_key: string
  old_value: unknown
  new_value: unknown
  confidence: number | null
  source_type: string
  source_id: string | null
  created_at: string
}

const isSuccessStatus = (status: number) => status >= 200 && status < 300

const failUnexpectedStatus = (status: number, path: string) =>
  Effect.fail(new Error(`Request ${path} failed with status ${status}`))

export const learnerProfileAtom = Atom.family((projectId: string) =>
  runtime.atom(
    Effect.gen(function* () {
      const { httpClient } = yield* ApiClientService
      const path = `/api/v1/projects/${projectId}/learner-profile`
      const response = yield* httpClient.get(path)
      if (response.status === 404) {
        return null as LearnerProfile | null
      }
      if (!isSuccessStatus(response.status)) {
        return yield* failUnexpectedStatus(response.status, path)
      }
      return (yield* response.json) as LearnerProfile
    }),
  ),
)

export const learnerProfileRevisionsAtom = Atom.family((projectId: string) =>
  runtime.atom(
    Effect.gen(function* () {
      const { httpClient } = yield* ApiClientService
      const path = `/api/v1/projects/${projectId}/learner-profile/revisions`
      const response = yield* httpClient.get(path)
      if (response.status === 404) {
        return [] as Array<LearnerProfileRevision>
      }
      if (!isSuccessStatus(response.status)) {
        return yield* failUnexpectedStatus(response.status, path)
      }
      return (yield* response.json) as Array<LearnerProfileRevision>
    }),
  ),
)

export const refreshLearnerProfileAtom = runtime.fn(
  Effect.fn(
    function* (projectId: string) {
      const registry = yield* Registry.AtomRegistry
      const { httpClient } = yield* ApiClientService
      const path = `/api/v1/projects/${projectId}/learner-profile/refresh`
      const response = yield* httpClient.post(path)
      if (!isSuccessStatus(response.status)) {
        return yield* failUnexpectedStatus(response.status, path)
      }
      const profile = (yield* response.json) as LearnerProfile

      registry.refresh(learnerProfileAtom(projectId))
      registry.refresh(learnerProfileRevisionsAtom(projectId))
      registry.refresh(knowledgeGraphAtom(projectId))
      registry.refresh(practiceRecordsRemoteAtom(projectId))

      return profile
    },
    withToast({
      onWaiting: () => '正在刷新学生画像...',
      onSuccess: '学生画像已刷新',
      onFailure: '学生画像刷新失败',
    }),
  ),
)
