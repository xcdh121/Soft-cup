import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useRouterState } from '@tanstack/react-router'
import { Cause } from 'effect'
import {
  BarChart3Icon,
  BookOpenTextIcon,
  BotIcon,
  ChevronRightIcon,
  FileStackIcon,
  HistoryIcon,
  ListChecksIcon,
  MessageSquareIcon,
  NetworkIcon,
  SparklesIcon,
  UserRoundIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { ChatDto } from '@/integrations/api/client'
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

const getCurrentProjectId = (pathname: string) => {
  const match = pathname.match(/^\/dashboard\/p\/([^/]+)/)
  return match?.[1] ?? null
}

const ChatItem = ({ chat }: { chat: ChatDto }) => {
  const { location } = useRouterState()

  return (
    <SidebarMenuSubItem>
      <SidebarMenuSubButton
        asChild
        size="md"
        isActive={location.pathname.endsWith(`/c/${chat.id}`)}
      >
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

const ProjectNavSection = ({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) => (
  <section aria-label={title} className="space-y-1">
    <h3 className="px-2 text-[11px] font-semibold tracking-wide text-sidebar-foreground/55">
      {title}
    </h3>
    <SidebarMenu>{children}</SidebarMenu>
  </section>
)

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
            <span className="truncate">
              {currentProject?.name ?? '当前项目'}
            </span>
            <ChevronRightIcon className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/current-project:rotate-90" />
          </CollapsibleTrigger>
        </SidebarGroupLabel>
        <CollapsibleContent>
          <div className="space-y-4 pt-1">
            <ProjectNavSection title="AI 助学">
              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="AI 导师"
                  isActive={
                    location.pathname === `/dashboard/p/${currentProjectId}`
                  }
                >
                  <Link
                    to="/dashboard/p/$projectId"
                    params={{ projectId: currentProjectId }}
                  >
                    <BotIcon className="size-4 opacity-70" />
                    <span>AI 导师</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <Collapsible defaultOpen className="group/chat-history">
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip="对话记录"
                      isActive={location.pathname.includes('/c/')}
                    >
                      <MessageSquareIcon className="size-4 opacity-70" />
                      <span>对话记录</span>
                      <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/chat-history:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      <ProjectChatList projectId={currentProjectId} />
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>
            </ProjectNavSection>

            <ProjectNavSection title="学习中心">
              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="文档学习"
                  isActive={
                    location.pathname ===
                    `/dashboard/p/${currentProjectId}/custom-documents`
                  }
                >
                  <Link
                    to="/dashboard/p/$projectId/custom-documents"
                    params={{ projectId: currentProjectId }}
                  >
                    <FileStackIcon className="size-4 opacity-70" />
                    <span>文档学习</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="知识图谱"
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

              <Collapsible defaultOpen className="group/learning-evaluation">
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip="学习效果评估"
                      isActive={location.pathname.includes(
                        '/learning-evaluation',
                      )}
                    >
                      <BarChart3Icon className="size-4 opacity-70" />
                      <span>学习效果评估</span>
                      <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/learning-evaluation:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton
                          asChild
                          size="md"
                          isActive={
                            location.pathname ===
                              `/dashboard/p/${currentProjectId}/learning-evaluation` ||
                            location.pathname.endsWith(
                              '/learning-evaluation/history',
                            )
                          }
                        >
                          <Link
                            to="/dashboard/p/$projectId/learning-evaluation/history"
                            params={{ projectId: currentProjectId }}
                          >
                            <HistoryIcon className="size-4 opacity-70" />
                            <span>历史错题分析</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton
                          asChild
                          size="md"
                          isActive={
                            location.pathname.endsWith(
                              '/learning-evaluation/practice',
                            ) ||
                            location.pathname.endsWith(
                              '/learning-evaluation/programming',
                            ) ||
                            location.pathname.endsWith(
                              '/learning-evaluation/choice',
                            )
                          }
                        >
                          <Link
                            to="/dashboard/p/$projectId/learning-evaluation/practice"
                            params={{ projectId: currentProjectId }}
                          >
                            <ListChecksIcon className="size-4 opacity-70" />
                            <span>题目练习</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>
            </ProjectNavSection>

            <ProjectNavSection title="个性化学习">
              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="学生画像"
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
                  tooltip="学习计划"
                  isActive={
                    location.pathname ===
                    `/dashboard/p/${currentProjectId}/study-plan`
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
                  tooltip="资源包生成"
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
                    <span>资源包生成</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </ProjectNavSection>
          </div>
        </CollapsibleContent>
      </SidebarGroup>
    </Collapsible>
  )
}

export default CurrentProjectNav
