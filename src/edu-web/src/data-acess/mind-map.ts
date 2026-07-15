import { Atom, Registry } from '@effect-atom/atom-react'
import { Effect, Layer, Schema, Stream } from 'effect'
import { HttpBody } from '@effect/platform'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { MindMapCreate } from '@/integrations/api/client'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { ApiClientService } from '@/integrations/api/http'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

export const mindMapsAtom = Atom.family((projectId: string) =>
  Atom.make(
    Effect.gen(function* () {
      const { apiClient } = yield* ApiClientService
      const mindMaps =
        yield* apiClient.listMindMapsApiV1ProjectsProjectIdMindMapsGet(
          projectId,
        )
      return mindMaps
    }).pipe(Effect.provide(ApiClientService.Default)),
  ).pipe(Atom.keepAlive),
)

export const mindMapAtom = Atom.family((key: string) => {
  const [projectId, mindMapId] = key.split(':')
  return Atom.make(
    Effect.gen(function* () {
      const { apiClient } = yield* ApiClientService
      const mindMap =
        yield* apiClient.getMindMapApiV1ProjectsProjectIdMindMapsMindMapIdGet(
          projectId,
          mindMapId,
        )
      return mindMap
    }).pipe(Effect.provide(ApiClientService.Default)),
  ).pipe(Atom.keepAlive)
})

const MindMapProgressUpdate = Schema.Struct({
  event: Schema.NullishOr(Schema.String),
  status: Schema.String,
  message: Schema.String,
  mind_map_id: Schema.NullishOr(Schema.String),
  error: Schema.NullishOr(Schema.String),
  nodes: Schema.NullishOr(Schema.Array(Schema.Unknown)),
  edges: Schema.NullishOr(Schema.Array(Schema.Unknown)),
})

export const mindMapProgressAtom = Atom.make<{
  status: string
  message: string
  mindMapId?: string
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
  error?: string
} | null>(null)

export const generateMindMapStreamAtom = Atom.fn(
  (
    input: {
      projectId: string
      mindMapId?: string
      title?: string
      customInstructions?: string
    },
    _get,
  ) =>
    Effect.gen(function* () {
      const { httpClient } = yield* ApiClientService
      let streamError: string | undefined
      let streamedNodes: Array<Record<string, unknown>> = []
      let streamedEdges: Array<Record<string, unknown>> = []
      const body = HttpBody.unsafeJson(
        new MindMapCreate({
          title: input.title ?? 'AI 思维导图',
          description: input.customInstructions,
          custom_instructions: input.customInstructions,
        }),
      )
      const resp = yield* httpClient.post(
        input.mindMapId
          ? `/api/v1/projects/${input.projectId}/mind-maps/${input.mindMapId}/generate/stream`
          : `/api/v1/projects/${input.projectId}/mind-maps/stream`,
        { body },
      )

      const decoder = new TextDecoder()
      const respStream = resp.stream.pipe(
        Stream.map((value) => decoder.decode(value, { stream: true })),
        Stream.map((chunk) => {
          const chunkLines = chunk.split('\n')
          const res = chunkLines
            .map((line) =>
              line.startsWith('data: ') ? line.replace('data: ', '') : '',
            )
            .filter((line) => line !== '')
            .join('\n')
          return res
        }),
        Stream.filter((chunk) => chunk !== ''),
        Stream.flatMap((chunk) => {
          const lines = chunk.trim().split('\n')
          return Stream.fromIterable(lines).pipe(
            Stream.filter((line) => line.trim() !== ''),
            Stream.flatMap((line) =>
              Schema.decodeUnknown(Schema.parseJson(MindMapProgressUpdate))(
                line,
              ),
            ),
          )
        }),
        Stream.tap((progress) =>
          Effect.gen(function* () {
            const registry = yield* Registry.AtomRegistry
            if (progress.error) {
              streamError = progress.error
            }
            streamedNodes = [
              ...streamedNodes,
              ...((progress.nodes ?? []) as Array<Record<string, unknown>>),
            ]
            streamedEdges = [
              ...streamedEdges,
              ...((progress.edges ?? []) as Array<Record<string, unknown>>),
            ]
            registry.set(mindMapProgressAtom, {
              status: progress.status,
              message: progress.message,
              mindMapId: progress.mind_map_id ?? undefined,
              nodes: streamedNodes,
              edges: streamedEdges,
              error: progress.error ?? undefined,
            })
          }),
        ),
      )

      yield* Stream.runCollect(respStream)

      const registry = yield* Registry.AtomRegistry
      if (input.projectId) {
        registry.refresh(mindMapsAtom(input.projectId))
        if (input.mindMapId) {
          registry.refresh(mindMapAtom(`${input.projectId}:${input.mindMapId}`))
        }
      }
      registry.set(mindMapProgressAtom, null)
      if (streamError) {
        throw new Error(streamError)
      }
    }).pipe(Effect.provide(ApiClientService.Default)),
).pipe(Atom.keepAlive)

export const refreshMindMapAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; mindMapId: string }) {
    const registry = yield* Registry.AtomRegistry
    registry.refresh(mindMapAtom(`${input.projectId}:${input.mindMapId}`))
  }),
)

export const generateMindMapAtom = runtime.fn(
  Effect.fn(function* (input: {
    projectId: string
    title?: string
    description?: string
    customInstructions?: string
  }) {
    const registry = yield* Registry.AtomRegistry
    const { apiClient } = yield* ApiClientService
    const mindMap =
      yield* apiClient.createMindMapApiV1ProjectsProjectIdMindMapsPost(
        input.projectId,
        new MindMapCreate({
          title: input.title ?? '新思维导图',
          description: input.description,
          custom_instructions: input.customInstructions,
        }),
      )

    registry.refresh(mindMapsAtom(input.projectId))
    registry.refresh(mindMapAtom(`${input.projectId}:${mindMap.id}`))
    return mindMap
  }),
)
