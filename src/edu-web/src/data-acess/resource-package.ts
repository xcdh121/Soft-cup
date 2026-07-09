import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { withToast } from '@/lib/with-toast'
import { Atom, Registry } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer, Stream } from 'effect'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export type ResourcePackageStatus =
  | 'draft'
  | 'generating'
  | 'completed'
  | 'failed'

export type GeneratedResourceStatus =
  | 'pending'
  | 'generating'
  | 'completed'
  | 'failed'

export type GenerationMode = 'manual' | 'recommended' | 'remedial'
export type DifficultyLevel = 'beginner' | 'intermediate' | 'advanced'

export type ResourceType =
  | 'lecture_note'
  | 'mind_map'
  | 'practice_set'
  | 'flashcards'
  | 'ppt_outline'
  | 'pptx'
  | 'programming_questions'
  | 'code_lab'
  | 'reading_material'
  | 'video_script'
  | 'video_recommendations'

export type GeneratedResource = {
  id: string
  resource_package_id: string
  project_id: string
  user_id: string
  resource_type: ResourceType
  title: string
  summary: string | null
  status: GeneratedResourceStatus
  format: string
  content_text: string | null
  content_json: Record<string, unknown> | null
  file_url: string | null
  preview_url: string | null
  cover_image_url: string | null
  source_document_ids: Array<string>
  knowledge_point_ids: Array<string>
  difficulty_level: DifficultyLevel
  estimated_minutes: number | null
  version: number
  generation_order: number
  generator_agent: string | null
  generation_reason: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export type ResourcePackage = {
  id: string
  project_id: string
  user_id: string
  profile_id: string | null
  learning_path_id: string | null
  title: string
  description: string | null
  generation_mode: GenerationMode
  status: ResourcePackageStatus
  target_topic: string
  target_goal: string | null
  difficulty_level: DifficultyLevel
  estimated_minutes: number | null
  source_document_ids: Array<string>
  knowledge_point_ids: Array<string>
  weak_knowledge_point_ids: Array<string>
  preferred_resource_types: Array<ResourceType>
  generation_params: Record<string, unknown>
  agent_trace: Array<Record<string, unknown>>
  resource_count: number
  completed_resource_count: number
  failed_resource_count: number
  created_at: string
  updated_at: string
  completed_at: string | null
  resources: Array<GeneratedResource>
}

export type GenerateResourcePackageInput = {
  projectId: string
  profile_id?: string
  learning_path_id?: string
  diagnosis_id?: string
  title?: string
  description?: string
  target_topic: string
  target_goal?: string
  source_document_ids?: Array<string>
  chapter_ids?: Array<string>
  knowledge_point_ids?: Array<string>
  weak_knowledge_point_ids?: Array<string>
  resource_types?: Array<ResourceType>
  difficulty_level?: DifficultyLevel
  generation_mode?: GenerationMode
  estimated_minutes?: number
  custom_instructions?: string
  generation_params?: Record<string, unknown>
}

type ResourcePackageStreamEvent = {
  event: string
  package_id: string
  payload: Record<string, unknown>
}

export type AgentProgressStep = {
  agentName: string
  status: string
  summary: string
  phase?: string
  eventType?: string
}

export const resourcePackageProgressAtom = Atom.make<{
  status: ResourcePackageStatus
  packageId: string | null
  resources: Array<GeneratedResource>
  resourceStatuses: Partial<Record<ResourceType, GeneratedResourceStatus>>
  agentSteps: Array<AgentProgressStep>
  currentResourceType?: ResourceType
  error?: string
} | null>(null)

export const resourcePackagesAtom = Atom.family((projectId: string) =>
  runtime.atom(
    Effect.gen(function* () {
      const { httpClient } = yield* ApiClientService
      const response = yield* httpClient.get(
        `/api/v1/projects/${projectId}/resource-packages`,
      )
      return (yield* response.json) as Array<ResourcePackage>
    }),
  ),
)

export const generatedResourcesAtom = Atom.family((input: string) => {
  const [projectId, packageId] = input.split(':')

  return runtime.atom(
    Effect.gen(function* () {
      const { httpClient } = yield* ApiClientService
      const response = yield* httpClient.get(
        `/api/v1/projects/${projectId}/resource-packages/${packageId}/resources`,
      )
      return (yield* response.json) as Array<GeneratedResource>
    }),
  )
})

export const generateResourcePackageAtom = runtime.fn(
  Effect.fn(
    function* (input: GenerateResourcePackageInput) {
      const registry = yield* Registry.AtomRegistry
      const { httpClient } = yield* ApiClientService
      const requestedTypes = input.resource_types ?? [
        'lecture_note', 'mind_map', 'practice_set', 'ppt_outline',
        'programming_questions', 'code_lab',
      ]
      let resourceStatuses: Partial<Record<ResourceType, GeneratedResourceStatus>> =
        Object.fromEntries(requestedTypes.map((type) => [type, 'pending']))
      registry.set(resourcePackageProgressAtom, {
        status: 'generating', packageId: null, resources: [], resourceStatuses,
        agentSteps: [],
      })

      const body = HttpBody.unsafeJson({
        profile_id: input.profile_id,
        learning_path_id: input.learning_path_id,
        diagnosis_id: input.diagnosis_id,
        title: input.title,
        description: input.description,
        target_topic: input.target_topic,
        target_goal: input.target_goal,
        source_document_ids: input.source_document_ids ?? [],
        chapter_ids: input.chapter_ids ?? [],
        knowledge_point_ids: input.knowledge_point_ids ?? [],
        weak_knowledge_point_ids: input.weak_knowledge_point_ids ?? [],
        resource_types: input.resource_types ?? [
          'lecture_note',
          'mind_map',
          'practice_set',
          'ppt_outline',
          'programming_questions',
          'code_lab',
        ],
        difficulty_level: input.difficulty_level ?? 'intermediate',
        generation_mode: input.generation_mode ?? 'manual',
        estimated_minutes: input.estimated_minutes,
        custom_instructions: input.custom_instructions,
        generation_params: input.generation_params ?? {},
      })

      const response = yield* httpClient.post(
        `/api/v1/projects/${input.projectId}/resource-packages/generate/stream`,
        { body },
      )

      let buffer = ''
      let packageId: string | null = null
      let resources: Array<GeneratedResource> = []
      let streamError: string | undefined
      let agentSteps: Array<AgentProgressStep> = []
      const decoder = new TextDecoder()
      yield* response.stream.pipe(
        Stream.map((chunk) => {
          buffer += decoder.decode(chunk, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() ?? ''
          return blocks
        }),
        Stream.flatMap((blocks) => Stream.fromIterable(blocks)),
        Stream.map((block) =>
          block
            .split('\n')
            .filter((line) => line.startsWith('data: '))
            .map((line) => line.slice(6))
            .join('\n'),
        ),
        Stream.filter((line) => line.length > 0),
        Stream.tap((line) =>
          Effect.sync(() => {
            const event = JSON.parse(line) as ResourcePackageStreamEvent
            packageId = event.package_id || packageId
            if (event.event === 'agent_step') {
              const step: AgentProgressStep = {
                agentName: String(event.payload.agent_name ?? 'SupervisorAgent'),
                status: String(event.payload.status ?? 'running'),
                summary: String(event.payload.summary ?? ''),
                phase: event.payload.phase as string | undefined,
                eventType: event.payload.event_type as string | undefined,
              }
              const existingIndex = agentSteps.findIndex(
                (item) => item.agentName === step.agentName && item.status === 'running',
              )
              if (step.status !== 'running' && existingIndex >= 0) {
                agentSteps = agentSteps.map((item, index) =>
                  index === existingIndex ? step : item,
                )
              } else if (step.eventType !== 'artifact_updated') {
                agentSteps = [...agentSteps, step]
              }
            }
            if (
              ['resource_completed', 'resource_generating', 'resource_failed'].includes(
                event.event,
              )
            ) {
              const resource = event.payload.resource as GeneratedResource
              resources = [...resources.filter((item) => item.id !== resource.id), resource]
              resourceStatuses = {
                ...resourceStatuses,
                [resource.resource_type]: resource.status,
              }
            } else if (event.event === 'resource_started') {
              resourceStatuses = {
                ...resourceStatuses,
                [event.payload.resource_type as ResourceType]: 'generating',
              }
            }
            if (event.event === 'package_failed') {
              streamError = String(event.payload.error ?? 'Resource package generation failed')
            }
            registry.set(resourcePackageProgressAtom, {
              status:
                event.event === 'package_completed'
                  ? (event.payload.status as ResourcePackageStatus)
                  : event.event === 'package_failed'
                    ? 'failed'
                    : 'generating',
              packageId,
              resources,
              resourceStatuses,
              agentSteps,
              currentResourceType: event.payload.resource_type as
                | ResourceType
                | undefined,
              error: streamError,
            })
          }),
        ),
        Stream.runDrain,
      )
      if (streamError) throw new Error(streamError)
      if (!packageId) throw new Error('Resource package stream returned no package ID')

      const packageResponse = yield* httpClient.get(
        `/api/v1/projects/${input.projectId}/resource-packages/${packageId}`,
      )
      const resourcePackage = (yield* packageResponse.json) as ResourcePackage

      registry.refresh(resourcePackagesAtom(input.projectId))
      registry.refresh(
        generatedResourcesAtom(`${input.projectId}:${resourcePackage.id}`),
      )
      registry.set(resourcePackageProgressAtom, null)

      return resourcePackage
    },
    withToast({
      onWaiting: () => 'Generating resource package...',
      onSuccess: 'Resource package generated.',
      onFailure: 'Failed to generate resource package.',
    }),
  ),
)
