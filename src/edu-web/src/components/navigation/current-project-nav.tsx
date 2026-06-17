import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar'
import { chatsAtom } from '@/data-acess/chat'
import { projectsAtom } from '@/data-acess/project'
import type { ChatDto } from '@/integrations/api/client'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useRouterState } from '@tanstack/react-router'
import { Cause } from 'effect'
import {
  BotIcon,
  BarChart3Icon,
  BookOpenTextIcon,
  ChevronRightIcon,
  FolderKanbanIcon,
  MessageSquareIcon,
  NetworkIcon,
  SparklesIcon,
  UserRoundIcon,
} from 'lucide-react'

const getCurrentProjectId = (pathname: string) => {
  const match = pathname.match(/^\/dashboard\/p\/([^/]+)/)
  return match?.[1] ?? null
}

const ChatItem = ({ chat }: { chat: ChatDto }) => {
  return (
    <SidebarMenuSubItem>
      <SidebarMenuSubButton asChild size="md">
        <Link
          to="/dashboard/p/$projectId/c/$chatId"
          params={{
            projectId: chat.project_id,
            chatId: chat.id,
          }}
        >
          <span>{chat.title ?? '未命名聊天'}</span>
        </Link>
      </SidebarMenuSubButton>
    </SidebarMenuSubItem>
  )
}

const ProjectChatList = ({ projectId }: { projectId: string }) => {
  const chatsResult = useAtomValue(chatsAtom(projectId))

  return Result.builder(chatsResult)
    .onSuccess((chats) => (
      <>
        {chats.map((chat) => (
          <ChatItem key={chat.id} chat={chat} />
        ))}

        {chats.length === 0 && (
          <SidebarMenuSubItem>
            <SidebarMenuSubButton size="md">
              <span className="text-sm text-muted-foreground">还没有聊天</span>
            </SidebarMenuSubButton>
          </SidebarMenuSubItem>
        )}
      </>
    ))
    .onInitialOrWaiting(() => (
      <SidebarMenuSubItem>
        <SidebarMenuSubButton size="md">
          <span className="text-sm text-muted-foreground">正在加载聊天...</span>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    ))
    .onFailure((cause) => (
      <SidebarMenuSubItem>
        <SidebarMenuSubButton size="md">
          <span className="text-sm text-muted-foreground">
            聊天加载失败: {Cause.pretty(cause)}
          </span>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    ))
    .render()
}

export function CurrentProjectNav() {
  const { location } = useRouterState()
  const projectsResult = useAtomValue(projectsAtom)
  const currentProjectId = getCurrentProjectId(location.pathname)

  if (!currentProjectId) {
    return null
  }

  const currentProject = Result.isSuccess(projectsResult)
    ? projectsResult.value.find((project) => project.id === currentProjectId)
    : null

  return (
    <Collapsible defaultOpen className="group/current-project">
      <SidebarGroup className="group-data-[collapsible=icon]:hidden">
        <SidebarGroupLabel asChild>
          <CollapsibleTrigger className="flex w-full items-center gap-2 text-left">
            <span className="truncate">{currentProject?.name ?? '当前项目'}</span>
            <ChevronRightIcon className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/current-project:rotate-90" />
          </CollapsibleTrigger>
        </SidebarGroupLabel>
        <CollapsibleContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={location.pathname === `/dashboard/p/${currentProjectId}`}
              >
                <Link
                  to="/dashboard/p/$projectId"
                  params={{ projectId: currentProjectId }}
                >
                  <FolderKanbanIcon className="size-4 opacity-70" />
                  <span>项目概览</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname === `/dashboard/p/${currentProjectId}/study-plan`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/study-plan"
                  params={{ projectId: currentProjectId }}
                >
                  <BookOpenTextIcon className="size-4 opacity-70" />
                  <span>学习计划</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname ===
                  `/dashboard/p/${currentProjectId}/agent-orchestration`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/agent-orchestration"
                  params={{ projectId: currentProjectId }}
                >
                  <BotIcon className="size-4 opacity-70" />
                  <span>Agent 编排</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname ===
                  `/dashboard/p/${currentProjectId}/resource-packages`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/resource-packages"
                  params={{ projectId: currentProjectId }}
                >
                  <SparklesIcon className="size-4 opacity-70" />
                  <span>资源包</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname ===
                  `/dashboard/p/${currentProjectId}/learner-profile`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/learner-profile"
                  params={{ projectId: currentProjectId }}
                >
                  <UserRoundIcon className="size-4 opacity-70" />
                  <span>学生画像</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname ===
                  `/dashboard/p/${currentProjectId}/knowledge-graph`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/knowledge-graph"
                  params={{ projectId: currentProjectId }}
                >
                  <NetworkIcon className="size-4 opacity-70" />
                  <span>知识图谱</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname ===
                  `/dashboard/p/${currentProjectId}/learning-evaluation`
                }
              >
                <Link
                  to="/dashboard/p/$projectId/learning-evaluation"
                  params={{ projectId: currentProjectId }}
                >
                  <BarChart3Icon className="size-4 opacity-70" />
                  <span>学习效果评估</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <Collapsible defaultOpen className="group/collapsible">
              <SidebarMenuItem>
                <CollapsibleTrigger asChild>
                  <SidebarMenuButton tooltip="聊天">
                    <MessageSquareIcon className="size-4 opacity-70" />
                    <span>聊天</span>
                    <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    <ProjectChatList projectId={currentProjectId} />
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          </SidebarMenu>
        </CollapsibleContent>
      </SidebarGroup>
    </Collapsible>
  )
}

export default CurrentProjectNav
