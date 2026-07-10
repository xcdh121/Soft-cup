import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import {
  ArrowLeft,
  CheckIcon,
  HistoryIcon,
  Loader2Icon,
  MessageSquarePlusIcon,
  WrenchIcon,
} from 'lucide-react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { chatAtom, chatsAtom, createChatAtom } from '@/data-acess/chat'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const ChatHeaderContent = (props: { projectId: string; chatId: string }) => {
  const { projectId, chatId } = props
  const atomInput = useMemo(() => `${projectId}:${chatId}`, [projectId, chatId])
  const chatResult = useAtomValue(chatAtom(atomInput))

  return Result.builder(chatResult)
    .onSuccess((chat) => (
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage className="line-clamp-1 font-medium">
              {chat.title ?? '未命名聊天'}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    ))
    .onInitialOrWaiting(() => <Skeleton className="w-72 h-7" />)
    .render()
}

const ChatHistoryMenu = (props: { projectId: string; chatId: string }) => {
  const { projectId, chatId } = props
  const chatsResult = useAtomValue(chatsAtom(projectId))
  const createChat = useAtomSet(createChatAtom, { mode: 'promise' })
  const navigate = useNavigate()
  const [isCreating, setIsCreating] = useState(false)

  const handleCreateChat = async () => {
    if (isCreating) return

    setIsCreating(true)
    try {
      const chat = await createChat({ projectId })
      await navigate({
        to: '/dashboard/p/$projectId/c/$chatId',
        params: { projectId, chatId: chat.id },
      })
    } catch {
      toast.error('新建聊天失败，请稍后重试')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <HistoryIcon className="size-4" />
          <span className="hidden sm:inline">聊天记录</span>
          <span className="sr-only sm:hidden">聊天记录</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-80 max-w-[calc(100vw-2rem)]"
      >
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>聊天记录</span>
          {Result.isSuccess(chatsResult) && (
            <span className="text-xs font-normal text-muted-foreground">
              {chatsResult.value.length} 条
            </span>
          )}
        </DropdownMenuLabel>
        <DropdownMenuItem
          disabled={isCreating}
          onSelect={() => void handleCreateChat()}
          className="font-medium"
        >
          {isCreating ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <MessageSquarePlusIcon className="size-4" />
          )}
          新建聊天
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        {Result.isInitial(chatsResult) || chatsResult.waiting ? (
          <div className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
            <Loader2Icon className="size-4 animate-spin" />
            正在加载...
          </div>
        ) : Result.isFailure(chatsResult) ? (
          <p className="px-2 py-3 text-sm text-destructive">加载失败</p>
        ) : Result.isSuccess(chatsResult) && chatsResult.value.length > 0 ? (
          <div className="max-h-80 overflow-y-auto">
            {chatsResult.value.map((chat) => {
              const isActive = chat.id === chatId

              return (
                <DropdownMenuItem key={chat.id} asChild className="h-auto p-0">
                  <Link
                    to="/dashboard/p/$projectId/c/$chatId"
                    params={{ projectId, chatId: chat.id }}
                    className="flex w-full items-start gap-2 px-2 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">
                          {chat.title ?? '未命名聊天'}
                        </span>
                        <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                          {format(
                            new Date(chat.last_message_at ?? chat.updated_at),
                            'MM/dd',
                          )}
                        </span>
                      </div>
                      {chat.last_message_content && (
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {chat.last_message_content}
                        </p>
                      )}
                    </div>
                    {isActive && (
                      <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" />
                    )}
                  </Link>
                </DropdownMenuItem>
              )
            })}
          </div>
        ) : (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            暂无历史聊天
          </p>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

type ChatHeaderProps = {
  chatId: string
  projectId: string
  developerMode?: boolean
  onOpenToolActivity?: () => void
}

export const ChatHeader = (props: ChatHeaderProps) => {
  const { projectId, chatId, developerMode = false, onOpenToolActivity } = props

  return (
    <header className="bg-background sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-2">
      <div className="flex min-w-0 flex-1 items-center gap-2 px-3">
        <SidebarTrigger />
        <Button variant="ghost" size="icon" className="size-7" asChild>
          <Link to="/dashboard/p/$projectId" params={{ projectId }}>
            <ArrowLeft className="size-4" />
            <span className="sr-only">返回项目</span>
          </Link>
        </Button>
        <Separator
          orientation="vertical"
          className="mr-2 data-[orientation=vertical]:h-4"
        />
        <ChatHeaderContent projectId={projectId} chatId={chatId} />
      </div>
      <div className="flex shrink-0 items-center gap-1 px-3">
        {developerMode && onOpenToolActivity && (
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={onOpenToolActivity}
            title="工具调试"
          >
            <WrenchIcon className="size-4" />
            <span className="sr-only">打开工具调试</span>
          </Button>
        )}
        <ChatHistoryMenu projectId={projectId} chatId={chatId} />
      </div>
    </header>
  )
}
