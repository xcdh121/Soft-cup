import { useEffect, useState } from 'react'

type GeneratedResourceStatus = 'pending' | 'generating' | 'completed' | 'failed'

type GeneratedResourceTarget = 'note' | 'quiz' | 'flashcards' | 'mind_map'

type SnapshotState<T> = {
  checking: boolean
  data: T | null
  status: GeneratedResourceStatus | null
  timedOut: boolean
}

const isEmptySnapshot = (data: unknown) =>
  data == null || (Array.isArray(data) && data.length === 0)

export const useGeneratedResourceSnapshot = <T>({
  projectId,
  targetType,
  targetId,
  dataPath,
  intervalMs = 1000,
  pollWhenEmpty = false,
  maxPollingMs = 10 * 60 * 1000,
}: {
  projectId: string
  targetType: GeneratedResourceTarget
  targetId: string
  dataPath: string
  intervalMs?: number
  /** Poll standalone generated collections that do not own a generated_resources row. */
  pollWhenEmpty?: boolean
  /** Stop presenting an endless spinner if a queued task is lost or fails silently. */
  maxPollingMs?: number
}) => {
  const [retryVersion, setRetryVersion] = useState(0)
  const [state, setState] = useState<SnapshotState<T>>({
    checking: true,
    data: null,
    status: null,
    timedOut: false,
  })

  useEffect(() => {
    let cancelled = false
    let timerId: number | undefined
    const pollingStartedAt = Date.now()

    setState((current) => ({
      ...current,
      checking: true,
      timedOut: false,
    }))

    const poll = async () => {
      let shouldContinue = false
      try {
        const [statusResponse, dataResponse] = await Promise.all([
          fetch(
            `/api/v1/projects/${projectId}/generated-resources/by-target/${targetType}/${targetId}`,
          ),
          fetch(dataPath),
        ])

        if (cancelled) return

        const status = statusResponse.ok
          ? (
              (await statusResponse.json()) as {
                status: GeneratedResourceStatus
              }
            ).status
          : null
        const data = dataResponse.ok ? ((await dataResponse.json()) as T) : null
        const generationIsActive =
          status === 'pending' || status === 'generating'
        const standaloneCollectionIsEmpty =
          status === null && pollWhenEmpty && isEmptySnapshot(data)
        shouldContinue = generationIsActive || standaloneCollectionIsEmpty
        const timedOut =
          shouldContinue && Date.now() - pollingStartedAt >= maxPollingMs
        if (timedOut) shouldContinue = false
        setState({ checking: false, data, status, timedOut })
      } catch {
        // Keep the last good snapshot visible and retry managed generations.
        const timedOut = Date.now() - pollingStartedAt >= maxPollingMs
        shouldContinue = !timedOut
        setState((current) => ({
          ...current,
          checking: false,
          timedOut,
        }))
      } finally {
        if (!cancelled && shouldContinue) {
          timerId = window.setTimeout(poll, intervalMs)
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timerId !== undefined) window.clearTimeout(timerId)
    }
  }, [
    dataPath,
    intervalMs,
    maxPollingMs,
    pollWhenEmpty,
    projectId,
    retryVersion,
    targetId,
    targetType,
  ])

  const inferredStandaloneGeneration =
    pollWhenEmpty && state.status === null && isEmptySnapshot(state.data)

  return {
    ...state,
    isGenerating:
      !state.timedOut &&
      (state.status === 'pending' ||
        state.status === 'generating' ||
        inferredStandaloneGeneration),
    isManaged: state.status !== null,
    retry: () => setRetryVersion((current) => current + 1),
  }
}
