import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  BookOpenIcon,
  Clock3Icon,
  FolderIcon,
  GraduationCapIcon,
  PlusIcon,
} from 'lucide-react'
import { projectsAtom } from '@/data-acess/project'
import { usageAtom } from '@/data-acess/usage'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

type StudyStat = {
  label: string
  value: string
  description: string
  icon: typeof BookOpenIcon
}

const formatStudyDuration = (minutes: number) => {
  if (minutes < 60) {
    return `${minutes} 分钟`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60

  if (remainingMinutes === 0) {
    return `${hours} 小时`
  }

  return `${hours} 小时 ${remainingMinutes} 分钟`
}

export const DashboardPage = () => {
  const projectsResult = useAtomValue(projectsAtom)
  const usageResult = useAtomValue(usageAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const hasProjects =
    Result.isSuccess(projectsResult) && projectsResult.value.length > 0

  const todayStudyStats: Array<StudyStat> = Result.isSuccess(usageResult)
    ? (() => {
        const activityCount =
          usageResult.value.chat_messages.used +
          usageResult.value.flashcard_generations.used +
          usageResult.value.quiz_generations.used +
          usageResult.value.mindmap_generations.used

        const estimatedMinutes =
          usageResult.value.chat_messages.used * 6 +
          usageResult.value.flashcard_generations.used * 12 +
          usageResult.value.quiz_generations.used * 15 +
          usageResult.value.mindmap_generations.used * 10

        const masteredKnowledgePoints =
          usageResult.value.flashcard_generations.used * 3 +
          usageResult.value.quiz_generations.used * 2 +
          usageResult.value.mindmap_generations.used * 4

        return [
          {
            label: '已学内容',
            value: `${activityCount} 项`,
            description: '按今日学习活动汇总，后续可接入真实内容统计',
            icon: BookOpenIcon,
          },
          {
            label: '学习时长',
            value: formatStudyDuration(estimatedMinutes),
            description: '依据学习活动估算，后续可接入真实时长',
            icon: Clock3Icon,
          },
          {
            label: '掌握知识点',
            value: `${masteredKnowledgePoints} 个`,
            description: '当前为展示占位，后续可接入掌握度模型',
            icon: GraduationCapIcon,
          },
        ]
      })()
    : Result.isFailure(usageResult)
      ? [
          {
            label: '已学内容',
            value: '0 项',
            description: '暂时无法获取今日学习数据',
            icon: BookOpenIcon,
          },
          {
            label: '学习时长',
            value: '0 分钟',
            description: '暂时无法获取今日学习数据',
            icon: Clock3Icon,
          },
          {
            label: '掌握知识点',
            value: '0 个',
            description: '暂时无法获取今日学习数据',
            icon: GraduationCapIcon,
          },
        ]
      : [
          {
            label: '已学内容',
            value: '--',
            description: '正在加载今日学习概览',
            icon: BookOpenIcon,
          },
          {
            label: '学习时长',
            value: '--',
            description: '正在整理学习时长',
            icon: Clock3Icon,
          },
          {
            label: '掌握知识点',
            value: '--',
            description: '正在汇总掌握情况',
            icon: GraduationCapIcon,
          },
        ]

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
            <p className="mt-2 text-muted-foreground">
              管理项目，并快速查看今天的学习进展。
            </p>
          </div>
          {hasProjects && (
            <Button onClick={() => openCreateProjectDialog()}>
              <PlusIcon className="mr-2 h-4 w-4" />
              新建项目
            </Button>
          )}
        </div>

        <Card className="border-primary/15 bg-gradient-to-br from-primary/8 via-background to-background shadow-sm">
          <CardHeader className="space-y-2">
            <CardTitle className="text-xl">今日学习概览</CardTitle>
            <CardDescription>
              这里集中展示你今天已经学习的内容、投入的时间和掌握情况。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            {todayStudyStats.map((stat) => {
              const Icon = stat.icon

              return (
                <div
                  key={stat.label}
                  className="rounded-2xl border bg-card/80 p-5 backdrop-blur"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {stat.label}
                    </span>
                    <div className="rounded-full bg-primary/10 p-2 text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-semibold tracking-tight">
                    {stat.value}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {stat.description}
                  </p>
                </div>
              )
            })}
          </CardContent>
        </Card>

        <Card className="border-dashed">
          <CardHeader>
            <CardTitle>我们的资料</CardTitle>
            <CardDescription>
              这里预留给我们自己的资料内容，后续可以接入资料卡片、推荐内容或下载入口。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-2xl border border-dashed bg-muted/30 px-6 py-10 text-center">
              <p className="text-base font-medium">资料展示位预留中</p>
              <p className="mt-2 text-sm text-muted-foreground">
                当前先占位，等资料结构确定后直接填充到这里。
              </p>
            </div>
          </CardContent>
        </Card>

        {Result.isSuccess(projectsResult) ? (
          projectsResult.value.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>还没有项目</CardTitle>
                <CardDescription>
                  创建第一个项目，开始整理你的学习资料。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button onClick={() => openCreateProjectDialog()}>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  创建项目
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {projectsResult.value.map((project) => (
                <Card
                  key={project.id}
                  className="transition-shadow hover:shadow-md"
                >
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FolderIcon className="h-5 w-5" />
                      <Link
                        to="/dashboard/p/$projectId"
                        params={{ projectId: project.id }}
                        className="hover:underline"
                      >
                        {project.name}
                      </Link>
                    </CardTitle>
                    {project.description && (
                      <CardDescription>{project.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <Link
                      to="/dashboard/p/$projectId"
                      params={{ projectId: project.id }}
                    >
                      <Button variant="outline" className="w-full">
                        打开项目
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )
        ) : Result.isFailure(projectsResult) ? (
          <div className="py-12 text-center">
            <p className="text-destructive">项目加载失败</p>
          </div>
        ) : (
          <div className="py-12 text-center">
            <p className="text-muted-foreground">正在加载项目...</p>
          </div>
        )}
      </div>
    </div>
  )
}
