import { useEffect, useState } from 'react'
import type { NoteDto } from '@/integrations/api/client'
import { appendSseChunk } from '@/lib/sse'

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

    const pollFallback = async () => {
      while (!cancelled) {
        try {
          const [statusResponse, noteResponse] = await Promise.all([
            fetch(
              `/api/v1/projects/${projectId}/generated-resources/by-target/note/${noteId}`,
              { signal: controller.signal },
            ),
            fetch(`/api/v1/projects/${projectId}/notes/${noteId}`, {
              signal: controller.signal,
            }),
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
        const response = await fetch(
          `/api/v1/projects/${projectId}/generated-resources/by-target/note/${noteId}/stream`,
          {
            headers: { Accept: 'text/event-stream' },
            signal: controller.signal,
          },
        )
        if (!response.ok || !response.body) {
          await pollFallback()
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
        if (!terminal && !cancelled) await pollFallback()
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
