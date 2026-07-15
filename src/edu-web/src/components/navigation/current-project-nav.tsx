import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useRouterState } from '@tanstack/react-router'
import {
  BarChart3Icon,
  BookOpenTextIcon,
  BotIcon,
  ChevronRightIcon,
  FileScanIcon,
  FileStackIcon,
  HistoryIcon,
  LanguagesIcon,
  ListChecksIcon,
  NetworkIcon,
  ScanTextIcon,
  SparklesIcon,
  UserRoundIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
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
import { projectsAtom } from '@/data-acess/project'

const getCurrentProjectId = (pathname: string) => {
  const match = pathname.match(/^\/dashboard\/p\/([^/]+)/)
  return match?.[1] ?? null
}

const ProjectNavSection = ({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) => (
  <section aria-label={title} className="space-y-1">
    <h3 className="mx-1 flex h-8 items-center justify-center rounded-lg border border-[#aac2d9] bg-[#c7d9e9] px-2 text-center text-[11px] font-semibold tracking-[0.08em] text-[#163a5d] shadow-[0_1px_2px_rgba(15,23,42,0.06)] dark:border-[#3c5d7c] dark:bg-[#294663] dark:text-[#e5eef7]">
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

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="手写笔记识别"
                  isActive={
                    location.pathname ===
                    `/dashboard/p/${currentProjectId}/handwriting-recognition`
                  }
                >
                  <Link
                    to="/dashboard/p/$projectId/handwriting-recognition"
                    params={{ projectId: currentProjectId }}
                  >
                    <ScanTextIcon className="size-4 opacity-70" />
                    <span>手写笔记识别</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="PDF 文档识别"
                  isActive={
                    location.pathname ===
                    `/dashboard/p/${currentProjectId}/pdf-ocr`
                  }
                >
                  <Link
                    to="/dashboard/p/$projectId/pdf-ocr"
                    params={{ projectId: currentProjectId }}
                  >
                    <FileScanIcon className="size-4 opacity-70" />
                    <span>PDF 文档识别</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="文档翻译"
                  isActive={
                    location.pathname ===
                    `/dashboard/p/${currentProjectId}/document-translation`
                  }
                >
                  <Link
                    to="/dashboard/p/$projectId/document-translation"
                    params={{ projectId: currentProjectId }}
                  >
                    <LanguagesIcon className="size-4 opacity-70" />
                    <span>文档翻译</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
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
