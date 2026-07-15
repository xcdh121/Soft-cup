import { Atom, Registry } from '@effect-atom/atom-react'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Effect, Layer, Stream } from 'effect'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { appendSseChunk } from '@/lib/sse'

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
  skillId?: string
  skillDisplayName?: string
  toolCallId?: string
  toolName?: string
  toolDisplayName?: string
  evidenceCount?: number
  durationMs?: number | null
  fallbackUsed?: boolean
}

const getAgentProgressKey = (step: AgentProgressStep) => {
  if (step.toolCallId) return `tool:${step.toolCallId}`
  if (step.skillId && step.eventType?.startsWith('skill_')) {
    return `skill:${step.agentName}:${step.skillId}`
  }
  if (step.eventType === 'agent_step' || step.eventType === 'agent_skipped') {
    return `agent:${step.agentName}`
  }
  if (
    step.eventType === 'run_started' ||
    step.eventType === 'route_decided' ||
    step.eventType === 'run_completed' ||
    step.eventType === 'run_failed'
  ) {
    return `run:${step.agentName}`
  }
  return `${step.agentName}:${step.eventType ?? 'event'}:${step.phase ?? ''}`
}

export const upsertAgentProgressStep = (
  steps: Array<AgentProgressStep>,
  step: AgentProgressStep,
) => {
  if (step.eventType === 'artifact_updated') return steps
  const existingIndex = steps.findIndex(
    (item) => getAgentProgressKey(item) === getAgentProgressKey(step),
  )
  if (existingIndex < 0) return [...steps, step]
  return steps.map((item, index) => (index === existingIndex ? step : item))
}

export const resourcePackageProgressAtom = Atom.make<{
  projectId: string
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

export const refreshResourcePackagesAtom = runtime.fn(
  Effect.fn(function* (projectId: string) {
    const registry = yield* Registry.AtomRegistry
    registry.refresh(resourcePackagesAtom(projectId))
  }),
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
  Effect.fn(function* (input: GenerateResourcePackageInput) {
    const registry = yield* Registry.AtomRegistry
    const { httpClient } = yield* ApiClientService
    const requestedTypes = input.resource_types ?? [
      'lecture_note',
      'mind_map',
      'practice_set',
      'ppt_outline',
      'programming_questions',
      'code_lab',
    ]
    let resourceStatuses: Partial<
      Record<ResourceType, GeneratedResourceStatus>
    > = Object.fromEntries(requestedTypes.map((type) => [type, 'pending']))
    registry.set(resourcePackageProgressAtom, {
      projectId: input.projectId,
      status: 'generating',
      packageId: null,
      resources: [],
      resourceStatuses,
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
    let packageId = ''
    let resources: Array<GeneratedResource> = []
    let streamError: string | undefined
    let agentSteps: Array<AgentProgressStep> = []
    const decoder = new TextDecoder()
    yield* response.stream.pipe(
      Stream.map((chunk) => {
        const parsed = appendSseChunk(
          buffer,
          decoder.decode(chunk, { stream: true }),
        )
        buffer = parsed.buffer
        return parsed.blocks
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
              skillId: event.payload.skill_id as string | undefined,
              skillDisplayName: event.payload.skill_display_name as
                | string
                | undefined,
              toolCallId: event.payload.tool_call_id as string | undefined,
              toolName: event.payload.tool_name as string | undefined,
              toolDisplayName: event.payload.tool_display_name as
                | string
                | undefined,
              evidenceCount: event.payload.evidence_count as number | undefined,
              durationMs: event.payload.duration_ms as
                | number
                | null
                | undefined,
              fallbackUsed: event.payload.fallback_used as boolean | undefined,
            }
            agentSteps = upsertAgentProgressStep(agentSteps, step)
          }
          if (
            [
              'resource_completed',
              'resource_generating',
              'resource_failed',
            ].includes(event.event)
          ) {
            const resource = event.payload.resource as GeneratedResource
            resources = [
              ...resources.filter((item) => item.id !== resource.id),
              resource,
            ]
            resourceStatuses = {
              ...resourceStatuses,
              [resource.resource_type]: resource.status,
            }
          } else if (event.event === 'resource_started') {
            resourceStatuses = {
              ...resourceStatuses,
              [event.payload.resource_type as ResourceType]: 'generating',
            }
          } else if (event.event === 'resource_delta') {
            const resourceId = String(event.payload.resource_id ?? '')
            const resourceType = event.payload.resource_type as ResourceType
            const existing = resources.find((item) => item.id === resourceId)
            const now = new Date().toISOString()
            const partialResource: GeneratedResource = {
              id: resourceId,
              resource_package_id: packageId,
              project_id: input.projectId,
              user_id: existing?.user_id ?? '',
              resource_type: resourceType,
              title: String(
                event.payload.title ?? existing?.title ?? '正在生成笔记',
              ),
              summary: existing?.summary ?? null,
              status: 'generating',
              format: existing?.format ?? 'markdown',
              content_text: String(
                event.payload.content ?? existing?.content_text ?? '',
              ),
              content_json:
                event.payload.content_json &&
                typeof event.payload.content_json === 'object'
                  ? (event.payload.content_json as Record<string, unknown>)
                  : (existing?.content_json ?? null),
              file_url: existing?.file_url ?? null,
              preview_url:
                typeof event.payload.preview_url === 'string'
                  ? event.payload.preview_url
                  : (existing?.preview_url ?? null),
              cover_image_url: existing?.cover_image_url ?? null,
              source_document_ids: existing?.source_document_ids ?? [],
              knowledge_point_ids: existing?.knowledge_point_ids ?? [],
              difficulty_level:
                existing?.difficulty_level ??
                input.difficulty_level ??
                'intermediate',
              estimated_minutes: existing?.estimated_minutes ?? null,
              version: existing?.version ?? 1,
              generation_order: existing?.generation_order ?? 0,
              generator_agent: existing?.generator_agent ?? 'ResourceAgent',
              generation_reason: existing?.generation_reason ?? null,
              error_message: null,
              created_at: existing?.created_at ?? now,
              updated_at: now,
              completed_at: null,
            }
            resources = [
              ...resources.filter((item) => item.id !== resourceId),
              partialResource,
            ]
            resourceStatuses = {
              ...resourceStatuses,
              [resourceType]: 'generating',
            }
          }
          if (event.event === 'package_failed') {
            streamError = String(
              event.payload.error ?? 'Resource package generation failed',
            )
          }
          registry.set(resourcePackageProgressAtom, {
            projectId: input.projectId,
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
    if (packageId.length === 0)
      throw new Error('Resource package stream returned no package ID')

    const packageResponse = yield* httpClient.get(
      `/api/v1/projects/${input.projectId}/resource-packages/${packageId}`,
    )
    const resourcePackage = (yield* packageResponse.json) as ResourcePackage

    registry.refresh(resourcePackagesAtom(input.projectId))
    registry.refresh(
      generatedResourcesAtom(`${input.projectId}:${resourcePackage.id}`),
    )
    registry.set(resourcePackageProgressAtom, {
      projectId: input.projectId,
      status: resourcePackage.status,
      packageId: resourcePackage.id,
      resources: resourcePackage.resources,
      resourceStatuses: Object.fromEntries(
        resourcePackage.resources.map((resource) => [
          resource.resource_type,
          resource.status,
        ]),
      ),
      agentSteps,
    })

    return resourcePackage
  }),
)
