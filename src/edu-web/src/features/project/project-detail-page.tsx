import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useNavigate } from '@tanstack/react-router'
import { Loader2Icon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { currentProjectIdAtom } from '@/data-acess/project'
import { chatsAtom, createChatAtom } from '@/data-acess/chat'
import { Button } from '@/components/ui/button'

type ProjectDetailPageProps = {
  projectId: string
}

export const ProjectDetailPage = ({ projectId }: ProjectDetailPageProps) => {
  const chatsResult = useAtomValue(chatsAtom(projectId))
  const createChat = useAtomSet(createChatAtom, { mode: 'promise' })
  const setCurrentProject = useAtomSet(currentProjectIdAtom)
  const navigate = useNavigate()
  const isOpeningChat = useRef(false)
  const [openError, setOpenError] = useState<string | null>(null)
  const [openAttempt, setOpenAttempt] = useState(0)

  useEffect(() => {
    setCurrentProject(projectId)
    isOpeningChat.current = false
    setOpenError(null)
  }, [projectId, setCurrentProject])

  useEffect(() => {
    if (!Result.isSuccess(chatsResult) || isOpeningChat.current) return

    isOpeningChat.current = true

    const openChat = async () => {
      try {
        const chat = chatsResult.value[0] ?? (await createChat({ projectId }))

        await navigate({
          to: '/dashboard/p/$projectId/c/$chatId',
          params: { projectId, chatId: chat.id },
          replace: true,
        })
      } catch {
        isOpeningChat.current = false
        setOpenError('无法打开聊天，请稍后重试')
      }
    }

    void openChat()
  }, [chatsResult, createChat, navigate, openAttempt, projectId])

  const retryOpenChat = () => {
    isOpeningChat.current = false
    setOpenError(null)
    setOpenAttempt((attempt) => attempt + 1)
  }

  if (Result.isFailure(chatsResult)) {
    return (
      <div className="flex h-full items-center justify-center text-destructive">
        聊天记录加载失败
      </div>
    )
  }

  if (openError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-destructive">{openError}</p>
        <Button variant="outline" size="sm" onClick={retryOpenChat}>
          重试
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
      <Loader2Icon className="size-4 animate-spin" />
      <span>正在进入聊天...</span>
    </div>
  )
}
