import { useEffect, useState } from 'react'
import type { NoteDto } from '@/integrations/api/client'
import { env } from '@/env'
import { authClient } from '@/lib/auth-client'
import { appendSseChunk } from '@/lib/sse'

const serverUrl = (env.VITE_SERVER_URL ?? window.location.origin).replace(
  /\/$/,
  '',
)

type NoteGenerationStatus = 'pending' | 'generating' | 'completed' | 'failed'

export type GeneratedNoteSnapshot = {
  event: 'note_snapshot'
  resource_id: string
  note_id: string
  status: NoteGenerationStatus
  title: string
  description: string | null
  content: string
  updated_at: string
}

export const useGeneratedNoteStream = ({
  projectId,
  noteId,
}: {
  projectId: string
  noteId: string
}) => {
  const [snapshot, setSnapshot] = useState<GeneratedNoteSnapshot | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    const getHeaders = async () => {
      const { data } = await authClient.auth.getSession()
      return {
        Accept: 'application/json',
        ...(data.session?.access_token
          ? { Authorization: `Bearer ${data.session.access_token}` }
          : {}),
      }
    }

    const pollFallback = async (headers?: Record<string, string>) => {
      const requestHeaders = headers ?? (await getHeaders())
      while (!cancelled) {
        try {
          const [statusResponse, noteResponse] = await Promise.all([
            fetch(
              `${serverUrl}/api/v1/projects/${projectId}/generated-resources/by-target/note/${noteId}`,
              { headers: requestHeaders, signal: controller.signal },
            ),
            fetch(
              `${serverUrl}/api/v1/projects/${projectId}/notes/${noteId}`,
              { headers: requestHeaders, signal: controller.signal },
            ),
          ])
          if (!statusResponse.ok || !noteResponse.ok) return

          const resource = (await statusResponse.json()) as {
            id: string
            status: NoteGenerationStatus
          }
          const note = (await noteResponse.json()) as NoteDto
          setSnapshot({
            event: 'note_snapshot',
            resource_id: resource.id,
            note_id: note.id,
            status: resource.status,
            title: note.title,
            description: note.description ?? null,
            content: note.content,
            updated_at: note.updated_at,
          })
          if (resource.status === 'completed' || resource.status === 'failed') {
            return
          }
        } catch {
          if (controller.signal.aborted) return
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
      }
    }

    const connect = async () => {
      try {
        const headers = await getHeaders()
        const response = await fetch(
          `${serverUrl}/api/v1/projects/${projectId}/generated-resources/by-target/note/${noteId}/stream`,
          {
            headers: { ...headers, Accept: 'text/event-stream' },
            signal: controller.signal,
          },
        )
        if (!response.ok || !response.body) {
          await pollFallback(headers)
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let terminal = false
        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          const parsed = appendSseChunk(
            buffer,
            decoder.decode(value, { stream: true }),
          )
          buffer = parsed.buffer
          for (const block of parsed.blocks) {
            const data = block
              .split('\n')
              .filter((line) => line.startsWith('data: '))
              .map((line) => line.slice(6))
              .join('\n')
            if (!data) continue
            const next = JSON.parse(data) as GeneratedNoteSnapshot
            setSnapshot(next)
            terminal = next.status === 'completed' || next.status === 'failed'
          }
        }
        if (!terminal && !cancelled) await pollFallback(headers)
      } catch {
        if (!controller.signal.aborted) await pollFallback()
      }
    }

    void connect()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [noteId, projectId])

  return {
    snapshot,
    isGenerating:
      snapshot?.status === 'pending' || snapshot?.status === 'generating',
  }
}
