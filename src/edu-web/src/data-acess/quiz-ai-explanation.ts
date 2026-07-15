import { HttpBody } from '@effect/platform'
import { Effect, Stream } from 'effect'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'

export type AiExplanationMessage = {
  role: 'user' | 'assistant'
  content: string
}

type AiStreamEvent =
  | { type: 'model'; model: string }
  | { type: 'status'; message: string }
  | { type: 'delta'; content: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

const runtime = makeAtomRuntime(ApiClientService.Default)

export const streamQuizAiExplanationAtom = runtime.fn(
  Effect.fn(function* (input: {
    projectId: string
    quizId: string
    questionId: string
    question?: string
    history: Array<AiExplanationMessage>
    onDelta: (text: string) => void
    onModel: (model: string) => void
    onStatus: (status: string) => void
  }) {
    const { httpClient } = yield* ApiClientService
    const response = yield* httpClient.post(
      `/api/v1/projects/${input.projectId}/quizzes/${input.quizId}/questions/${input.questionId}/ai-explanation`,
      {
        body: HttpBody.unsafeJson({
          question: input.question,
          history: input.history,
        }),
      },
    )

    const decoder = new TextDecoder()
    let buffer = ''
    const streamState: { error?: string } = {}

    const processEvent = (block: string) => {
      const data = block
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      if (!data) return
      const event = JSON.parse(data) as AiStreamEvent
      if (event.type === 'delta') input.onDelta(event.content)
      if (event.type === 'model') input.onModel(event.model)
      if (event.type === 'status') input.onStatus(event.message)
      if (event.type === 'error') streamState.error = event.message
    }

    yield* response.stream.pipe(
      Stream.runForEach((bytes) =>
        Effect.sync(() => {
          buffer += decoder.decode(bytes, { stream: true })
          const blocks = buffer.split(/\r?\n\r?\n/)
          buffer = blocks.pop() ?? ''
          blocks.forEach(processEvent)
        }),
      ),
    )
    buffer += decoder.decode()
    if (buffer.trim()) processEvent(buffer)
    if (streamState.error) throw new Error(streamState.error)
  }),
)
