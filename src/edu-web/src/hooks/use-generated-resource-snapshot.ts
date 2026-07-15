import { useEffect, useState } from 'react'

type GeneratedResourceStatus = 'pending' | 'generating' | 'completed' | 'failed'

type GeneratedResourceTarget = 'note' | 'quiz' | 'flashcards' | 'mind_map'

type SnapshotState<T> = {
  checking: boolean
  data: T | null
  status: GeneratedResourceStatus | null
}

export const useGeneratedResourceSnapshot = <T>({
  projectId,
  targetType,
  targetId,
  dataPath,
  intervalMs = 1000,
}: {
  projectId: string
  targetType: GeneratedResourceTarget
  targetId: string
  dataPath: string
  intervalMs?: number
}) => {
  const [state, setState] = useState<SnapshotState<T>>({
    checking: true,
    data: null,
    status: null,
  })

  useEffect(() => {
    let cancelled = false
    let timerId: number | undefined

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
        shouldContinue = status === 'pending' || status === 'generating'
        setState({ checking: false, data, status })
      } catch {
        // Keep the last good snapshot visible and retry managed generations.
        shouldContinue = true
        setState((current) => ({ ...current, checking: false }))
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
  }, [dataPath, intervalMs, projectId, targetId, targetType])

  return {
    ...state,
    isGenerating: state.status === 'pending' || state.status === 'generating',
    isManaged: state.status !== null,
  }
}
