import { Response } from '@/components/ai-elements/response'
import { noteAtom, refreshNoteAtom } from '@/data-acess/note'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'

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
  const refreshNote = useAtomSet(refreshNoteAtom, { mode: 'promise' })

  useEffect(() => {
    if (!Result.isSuccess(noteResult)) return
    if (!noteResult.value) return
    if (noteResult.value.content.trim()) return

    const intervalId = window.setInterval(() => {
      refreshNote({ projectId, noteId }).catch(() => {
        // Keep the current note visible if a transient refresh fails.
      })
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [noteId, noteResult, projectId, refreshNote])

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
      if (!note) {
        return (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <p>未找到笔记</p>
          </div>
        )
      }

      return (
        <div className={`flex flex-col space-y-4 ${className || ''}`}>
          {note.description && (
            <div className="text-muted-foreground text-sm">
              {note.description}
            </div>
          )}
          {note.content.trim() ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <Response>{note.content}</Response>
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
