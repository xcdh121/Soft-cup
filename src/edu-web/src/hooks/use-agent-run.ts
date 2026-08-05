import { useCallback, useEffect, useRef, useState } from 'react'
import {
  agentRunsApi,
  type AgentRun,
  type AgentRunEvent,
  type AgentRunStep,
} from '@/data-acess/agent-runs'
import { appendSseChunk } from '@/lib/sse'

type ConnectionState = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'closed'

export const useAgentRun = (runId: string | null) => {
  const [run, setRun] = useState<AgentRun | null>(null)
  const [steps, setSteps] = useState<Array<AgentRunStep>>([])
  const [events, setEvents] = useState<Array<AgentRunEvent>>([])
  const [error, setError] = useState<string | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('idle')
  const cursorRef = useRef(0)

  const refresh = useCallback(async () => {
    if (!runId) return
    const [nextRun, nextSteps, missed] = await Promise.all([
      agentRunsApi.get(runId),
      agentRunsApi.steps(runId),
      agentRunsApi.events(runId, cursorRef.current),
    ])
    setRun(nextRun)
    setSteps(nextSteps)
    if (missed.length) {
      cursorRef.current = Math.max(
        cursorRef.current,
        ...missed.map((event) => event.sequence),
      )
      setEvents((current) => {
        const merged = new Map(
          [...current, ...missed].map((event) => [event.sequence, event]),
        )
        return [...merged.values()].sort((a, b) => a.sequence - b.sequence)
      })
    }
  }, [runId])

  useEffect(() => {
    if (!runId) {
      setRun(null)
      setSteps([])
      setEvents([])
      setConnection('idle')
      return
    }
    cursorRef.current = 0
    setEvents([])
    const controller = new AbortController()

    const connect = async () => {
      let attempt = 0
      while (!controller.signal.aborted) {
        try {
          setConnection(attempt ? 'reconnecting' : 'connecting')
          await refresh()
          const token = await agentRunsApi.accessToken()
          const response = await fetch(
            agentRunsApi.streamUrl(runId, cursorRef.current),
            {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
              signal: controller.signal,
            },
          )
          if (!response.ok || !response.body) {
            throw new Error(`事件连接失败（${response.status}）`)
          }
          setConnection('live')
          setError(null)
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          while (!controller.signal.aborted) {
            const { done, value } = await reader.read()
            if (done) break
            const parsed = appendSseChunk(
              buffer,
              decoder.decode(value, { stream: true }),
            )
            buffer = parsed.buffer
            for (const block of parsed.blocks) {
              const dataLine = block
                .split('\n')
                .find((line) => line.startsWith('data: '))
              if (!dataLine) continue
              const event = JSON.parse(dataLine.slice(6)) as AgentRunEvent
              if (event.sequence <= cursorRef.current) continue
              cursorRef.current = event.sequence
              setEvents((current) => [...current, event])
              await refresh()
            }
          }
          const latest = await agentRunsApi.get(runId)
          setRun(latest)
          if (
            ['completed', 'partially_completed', 'failed', 'cancelled'].includes(
              latest.status,
            )
          ) {
            setConnection('closed')
            return
          }
        } catch (caught) {
          if (controller.signal.aborted) return
          setError(caught instanceof Error ? caught.message : '运行连接已中断')
        }
        attempt += 1
        setConnection('reconnecting')
        await new Promise((resolve) =>
          window.setTimeout(resolve, Math.min(5000, 500 * 2 ** attempt)),
        )
      }
    }
    void connect()
    return () => controller.abort()
  }, [refresh, runId])

  return { run, steps, events, error, connection, refresh }
}
