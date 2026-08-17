import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon, RefreshCwIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { noteAtom, noteProgressAtom, refreshNoteAtom } from '@/data-acess/note'
import { Response } from '@/components/ai-elements/response'
import { useGeneratedNoteStream } from '@/hooks/use-generated-note-stream'
import { Button } from '@/components/ui/button'

const NOTE_GENERATION_TIMEOUT_MS = 10 * 60 * 1000

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
  const emptySince = useRef<number | null>(null)
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (noteStream.snapshot) return
    if (!Result.isSuccess(noteResult)) return
    if (noteResult.value.content.trim()) {
      emptySince.current = null
      setTimedOut(false)
      return
    }

    emptySince.current ??= Date.now()

    const intervalId = window.setInterval(() => {
      if (
        emptySince.current &&
        Date.now() - emptySince.current >= NOTE_GENERATION_TIMEOUT_MS
      ) {
        setTimedOut(true)
        window.clearInterval(intervalId)
        return
      }
      refreshNote({ projectId, noteId }).catch(() => {
        // Keep the current note visible if a transient refresh fails.
      })
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [noteId, noteResult, noteStream.snapshot, projectId, refreshNote])

  const retry = () => {
    emptySince.current = Date.now()
    setTimedOut(false)
    void refreshNote({ projectId, noteId })
  }

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
          {noteStream.isGenerating && content.trim() ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              <span>笔记正在生成，内容会持续更新…</span>
            </div>
          ) : null}
          {content.trim() ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <Response>{content}</Response>
            </div>
          ) : noteStream.snapshot?.status === 'failed' || timedOut ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <div className="font-medium">
                {noteStream.snapshot?.status === 'failed'
                  ? '笔记生成失败'
                  : '笔记生成时间较长'}
              </div>
              <p className="max-w-md text-sm text-muted-foreground">
                {noteStream.snapshot?.status === 'failed'
                  ? '本次生成任务未能完成，请返回学习计划重新生成，或稍后重试。'
                  : '任务可能仍在队列中。你可以稍后再来，或立即重新检查生成结果。'}
              </p>
              <Button type="button" variant="outline" onClick={retry}>
                <RefreshCwIcon className="size-4" /> 重新检查
              </Button>
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              <span>
                {noteStream.isGenerating
                  ? '笔记模型正在准备，内容即将开始显示...'
                  : '笔记正在排队生成，内容完成后会自动显示...'}
              </span>
            </div>
          )}
        </div>
      )
    })
    .render()
}
