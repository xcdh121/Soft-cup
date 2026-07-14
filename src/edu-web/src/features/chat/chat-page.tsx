import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { Chatbot } from './chatbot'
import { ChatHeader } from './components/chat-header'
import { chatAtom } from '@/data-acess/chat'

type ChatPageProps = {
  projectId: string
  chatId: string
}

export const ChatPage = ({ projectId, chatId }: ChatPageProps) => {
  const chatKey = `${projectId}:${chatId}`
  const chatResult = useAtomValue(chatAtom(chatKey))

  // A background refresh runs after every completed response. Keep rendering
  // the successful snapshot while that refresh reconciles server data.
  const isLoading = chatResult.waiting && !Result.isSuccess(chatResult)
  const isError = Result.isFailure(chatResult)

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载聊天...</span>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-destructive">
        <span>聊天加载失败</span>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col max-h-screen">
      <ChatHeader chatId={chatId} projectId={projectId} />

      <div className="flex flex-1 flex-col min-h-0 max-h-[calc(100vh-3.5rem)] overflow-hidden w-full">
        <Chatbot chatId={chatId} projectId={projectId} />
      </div>
    </div>
  )
}
