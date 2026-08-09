import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useRouterState } from '@tanstack/react-router'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { projectsAtom } from '@/data-acess/project'

const getPageTrail = (pathname: string): Array<string> => {
  if (pathname === '/dashboard') return ['仪表盘']
  if (pathname === '/dashboard/my-courses') return ['我的课程']
  if (pathname === '/dashboard/course-library') return ['课程资料库']
  if (pathname === '/dashboard/agent-runtime') return ['智能协作观测台']
  if (pathname === '/dashboard/settings') return ['设置']

  if (/\/c\/[^/]+$/.test(pathname)) return ['对话记录', '对话详情']
  if (/\/d\/[^/]+$/.test(pathname)) return ['文档学习', '文档详情']
  if (/\/f\/[^/]+\/edit$/.test(pathname)) return ['我的资源', '编辑闪卡']
  if (/\/f\/[^/]+$/.test(pathname)) return ['我的资源', '闪卡学习']
  if (/\/q\/[^/]+\/edit$/.test(pathname)) return ['题目练习', '编辑题目']
  if (/\/q\/[^/]+$/.test(pathname)) return ['题目练习', '练习详情']
  if (/\/n\/[^/]+$/.test(pathname)) return ['我的资源', '笔记详情']
  if (/\/m\/[^/]+$/.test(pathname)) return ['我的资源', '思维导图详情']
  if (/\/r\/[^/]+$/.test(pathname)) return ['我的资源', '资源详情']
  if (/\/programming\/[^/]+$/.test(pathname)) {
    return ['题目练习', '编程练习']
  }
  if (pathname.endsWith('/custom-documents')) return ['文档学习']
  if (pathname.endsWith('/handwriting-recognition')) return ['手写笔记识别']
  if (pathname.endsWith('/pdf-ocr')) return ['PDF 文档识别']
  if (pathname.endsWith('/document-translation')) return ['文档翻译']
  if (pathname.endsWith('/my-resources')) return ['学习中心', '我的资源']
  if (pathname.endsWith('/knowledge-graph')) return ['知识图谱']
  if (pathname.endsWith('/learner-profile')) return ['学生画像']
  if (pathname.endsWith('/study-plan/customize')) {
    return ['学习计划', '定制学习计划']
  }
  if (pathname.endsWith('/study-plan')) return ['学习计划']
  if (pathname.includes('/learning-evaluation')) {
    if (pathname.endsWith('/history')) return ['学习效果评估', '历史错题分析']
    if (
      pathname.endsWith('/practice') ||
      pathname.endsWith('/programming') ||
      pathname.endsWith('/choice')
    ) {
      return ['学习效果评估', '题目练习']
    }
    return ['学习效果评估']
  }
  if (pathname.endsWith('/resource-packages')) return ['资源包']
  if (/\/p\/[^/]+$/.test(pathname)) return ['AI 导师']
  return ['当前页面']
}

export const AppBreadcrumbs = () => {
  const { location } = useRouterState()
  const projectsResult = useAtomValue(projectsAtom)
  const projectId = location.pathname.match(/^\/dashboard\/p\/([^/]+)/)?.[1]
  const projectName =
    projectId && Result.isSuccess(projectsResult)
      ? projectsResult.value.find((project) => project.id === projectId)?.name
      : null
  const trail = getPageTrail(location.pathname)

  return (
    <div className="flex h-10 shrink-0 items-center border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-sm dark:border-border dark:bg-background/90">
      <Breadcrumb className="min-w-0">
        <BreadcrumbList className="flex-nowrap">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/dashboard">首页</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          {projectId ? (
            <>
              <BreadcrumbSeparator />
              <BreadcrumbItem className="min-w-0">
                <BreadcrumbLink asChild>
                  <Link
                    to="/dashboard/p/$projectId"
                    params={{ projectId }}
                    className="max-w-48 truncate"
                  >
                    {projectName ?? '当前项目'}
                  </Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
            </>
          ) : null}
          {trail.map((label, index) => {
            const isCurrent = index === trail.length - 1
            return (
              <span key={`${label}-${index}`} className="contents">
                <BreadcrumbSeparator />
                <BreadcrumbItem className="min-w-0">
                  {isCurrent ? (
                    <BreadcrumbPage className="max-w-56 truncate font-medium">
                      {label}
                    </BreadcrumbPage>
                  ) : (
                    <span className="max-w-48 truncate text-muted-foreground">
                      {label}
                    </span>
                  )}
                </BreadcrumbItem>
              </span>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>
    </div>
  )
}
