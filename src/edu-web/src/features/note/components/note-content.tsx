import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'
import { noteAtom, noteProgressAtom, refreshNoteAtom } from '@/data-acess/note'
import { Response } from '@/components/ai-elements/response'
import { useGeneratedNoteStream } from '@/hooks/use-generated-note-stream'

type NoteContentProps = {
  noteId: string
  projectId: string
  className?: string
}

export const NoteContent = ({
  noteId,
  projectId,
  className,
}: NoteContentProps) => {
  const noteResult = useAtomValue(noteAtom(`${projectId}:${noteId}`))
  const streamProgress = useAtomValue(noteProgressAtom)
  const refreshNote = useAtomSet(refreshNoteAtom, { mode: 'promise' })
  const noteStream = useGeneratedNoteStream({ projectId, noteId })

  useEffect(() => {
    if (noteStream.snapshot) return
    if (!Result.isSuccess(noteResult)) return
    if (noteResult.value.content.trim()) return

    const intervalId = window.setInterval(() => {
      refreshNote({ projectId, noteId }).catch(() => {
        // Keep the current note visible if a transient refresh fails.
      })
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [noteId, noteResult, noteStream.snapshot, projectId, refreshNote])

  return Result.builder(noteResult)
    .onInitialOrWaiting(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载笔记...</span>
      </div>
    ))
    .onFailure(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-destructive">
        <span>笔记加载失败</span>
      </div>
    ))
    .onSuccess((note) => {
      const content = noteStream.snapshot
        ? noteStream.snapshot.content
        : streamProgress?.noteId === noteId && streamProgress.content
          ? streamProgress.content
          : note.content
      const description = noteStream.snapshot?.description ?? note.description

      return (
        <div
          className={`flex min-h-0 flex-col space-y-4 overflow-y-auto overscroll-contain pb-8 ${className || ''}`}
        >
          {description && (
            <Response className="text-muted-foreground text-sm">
              {description}
            </Response>
          )}
          {noteStream.isGenerating ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              <span>笔记正在生成，内容会持续更新…</span>
            </div>
          ) : null}
          {content.trim() ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <Response>{content}</Response>
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              <span>正在生成笔记内容...</span>
            </div>
          )}
        </div>
      )
    })
    .render()
}
