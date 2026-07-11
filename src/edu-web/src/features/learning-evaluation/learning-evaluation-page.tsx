import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Layers3,
  Star,
} from 'lucide-react'
import { useState } from 'react'
import type { EvaluationResource } from '@/data-acess/learning-evaluation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { learningEvaluationAtom } from '@/data-acess/learning-evaluation'
import { ProjectHeader } from '@/features/project/components/project-header'
import { cn } from '@/lib/utils'

type View = 'generated' | 'incomplete' | 'completed' | 'wrong'

const viewLabels: Record<View, string> = {
  generated: '已生成',
  incomplete: '未完成',
  completed: '已完成',
  wrong: '错题统计',
}

const typeLabels: Record<EvaluationResource['type'], string> = {
  quiz: '选择题',
  flashcard: '闪卡题',
  programming_questions: '编程题',
}

const getDifficultyStars = (difficulty?: string) => {
  const value = difficulty?.trim().toLowerCase()
  const numeric = Number(value)
  if (Number.isInteger(numeric) && numeric >= 1 && numeric <= 5) return numeric
  if (['very_easy', 'beginner', 'easy', '简单', '初级'].includes(value ?? '')) {
    return 1
  }
  if (
    ['medium', 'intermediate', 'normal', '中等', '中级'].includes(value ?? '')
  ) {
    return 3
  }
  if (
    ['very_hard', 'advanced', 'hard', 'expert', '困难', '高级'].includes(
      value ?? '',
    )
  ) {
    return 5
  }
  return 3
}

const getResourceStars = (resource: EvaluationResource) => {
  if (!resource.questions.length) return 3
  const total = resource.questions.reduce(
    (sum, question) => sum + getDifficultyStars(question.difficulty),
    0,
  )
  return Math.round(total / resource.questions.length)
}

const getKnowledgePoints = (resource: EvaluationResource) => {
  const points = resource.questions.flatMap(
    (question) => question.knowledgePoints,
  )
  return [...new Set(points)].filter(Boolean)
}

const getProgrammingSubmittedIds = (
  projectId: string,
  resource: EvaluationResource,
) => {
  if (
    resource.type !== 'programming_questions' ||
    typeof window === 'undefined'
  ) {
    return []
  }
  try {
    const value = window.localStorage.getItem(
      `programming-submitted:${projectId}:${resource.id}`,
    )
    const parsed = value ? JSON.parse(value) : []
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

const getResourceStats = (projectId: string, resource: EvaluationResource) => {
  const attemptCount = resource.questions.reduce(
    (sum, question) => sum + question.attemptCount,
    0,
  )
  const correctCount = resource.questions.reduce(
    (sum, question) => sum + question.correctCount,
    0,
  )
  const submittedCount = getProgrammingSubmittedIds(projectId, resource).length
  const completed =
    resource.type === 'programming_questions'
      ? resource.itemCount > 0 && submittedCount >= resource.itemCount
      : resource.status === 'completed'

  return {
    attemptCount:
      resource.type === 'programming_questions' ? submittedCount : attemptCount,
    accuracy: attemptCount
      ? Math.round((correctCount / attemptCount) * 100)
      : null,
    completed,
  }
}

const ResourceAction = ({
  projectId,
  resource,
  completed,
}: {
  projectId: string
  resource: EvaluationResource
  completed: boolean
}) => {
  const label = completed ? '重做' : '做题'
  const content = (
    <>
      {label}
      <ArrowUpRight className="size-3.5" />
    </>
  )

  if (resource.type === 'quiz') {
    return (
      <Button size="sm" variant="ghost" className="h-8 gap-1 px-2" asChild>
        <Link
          to="/dashboard/p/$projectId/q/$quizId"
          params={{ projectId, quizId: resource.id }}
        >
          {content}
        </Link>
      </Button>
    )
  }

  if (resource.type === 'flashcard') {
    return (
      <Button size="sm" variant="ghost" className="h-8 gap-1 px-2" asChild>
        <Link
          to="/dashboard/p/$projectId/f/$flashcardGroupId"
          params={{ projectId, flashcardGroupId: resource.id }}
        >
          {content}
        </Link>
      </Button>
    )
  }

  return (
    <Button size="sm" variant="ghost" className="h-8 gap-1 px-2" asChild>
      <Link
        to="/dashboard/p/$projectId/programming/$resourceId"
        params={{ projectId, resourceId: resource.id }}
      >
        {content}
      </Link>
    </Button>
  )
}

const ResourceList = ({
  projectId,
  resources,
}: {
  projectId: string
  resources: Array<EvaluationResource>
}) => {
  const navigate = useNavigate()

  const openResource = (resource: EvaluationResource) => {
    if (resource.type === 'quiz') {
      void navigate({
        to: '/dashboard/p/$projectId/q/$quizId',
        params: { projectId, quizId: resource.id },
      })
      return
    }
    if (resource.type === 'flashcard') {
      void navigate({
        to: '/dashboard/p/$projectId/f/$flashcardGroupId',
        params: { projectId, flashcardGroupId: resource.id },
      })
      return
    }
    void navigate({
      to: '/dashboard/p/$projectId/programming/$resourceId',
      params: { projectId, resourceId: resource.id },
    })
  }

  return (
    <Card className="overflow-hidden rounded-2xl">
      <Table className="table-fixed">
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-[22%] pl-4">题目组</TableHead>
            <TableHead className="w-[9%]">类型</TableHead>
            <TableHead className="w-[15%]">难度</TableHead>
            <TableHead className="w-[17%]">涉及知识点</TableHead>
            <TableHead className="w-[10%]">完成情况</TableHead>
            <TableHead className="w-[13%]">正确率</TableHead>
            <TableHead className="w-[7%]">次数</TableHead>
            <TableHead className="w-[7%] pr-3 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {resources.map((resource, index) => {
            const stars = getResourceStars(resource)
            const knowledgePoints = getKnowledgePoints(resource)
            const stats = getResourceStats(projectId, resource)

            return (
              <TableRow
                key={`${resource.type}-${resource.id}`}
                className="cursor-pointer"
                tabIndex={0}
                onClick={() => openResource(resource)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    openResource(resource)
                  }
                }}
              >
                <TableCell className="pl-4 align-middle">
                  <div className="line-clamp-2 whitespace-normal font-medium leading-5">
                    {index + 1}. {resource.name}
                  </div>
                </TableCell>
                <TableCell className="align-middle font-medium">
                  {typeLabels[resource.type]}
                </TableCell>
                <TableCell className="align-middle">
                  <div
                    className="flex items-center gap-1"
                    aria-label={`${stars} 星难度`}
                  >
                    {Array.from({ length: 5 }, (_, starIndex) => (
                      <Star
                        key={starIndex}
                        className={cn(
                          'size-3.5 text-muted-foreground/25',
                          starIndex < stars && 'fill-[#7DA0CA] text-[#5483B3]',
                        )}
                      />
                    ))}
                    <span className="text-xs text-muted-foreground">
                      {stars}/5
                    </span>
                  </div>
                </TableCell>
                <TableCell className="align-middle text-sm text-muted-foreground">
                  <span className="line-clamp-2 whitespace-normal">
                    {knowledgePoints.length
                      ? knowledgePoints.join('、')
                      : '暂未标注'}
                  </span>
                </TableCell>
                <TableCell
                  className={cn(
                    'align-middle font-medium',
                    stats.completed ? 'text-[#052659]' : 'text-[#5483B3]',
                  )}
                >
                  {stats.completed ? '已完成' : '未完成'}
                </TableCell>
                <TableCell className="align-middle">
                  <div className="mb-1 flex items-center gap-1 text-xs">
                    <span>
                      {stats.accuracy === null
                        ? resource.type === 'programming_questions'
                          ? '待评阅'
                          : '暂无作答'
                        : `${stats.accuracy}%`}
                    </span>
                    {stats.accuracy !== null ? (
                      <span className="text-muted-foreground">
                        (
                        {resource.questions.reduce(
                          (sum, question) => sum + question.correctCount,
                          0,
                        )}
                        /
                        {resource.questions.reduce(
                          (sum, question) => sum + question.attemptCount,
                          0,
                        )}
                        )
                      </span>
                    ) : null}
                  </div>
                  <Progress value={stats.accuracy ?? 0} className="h-1.5" />
                </TableCell>
                <TableCell className="align-middle font-medium">
                  {stats.attemptCount} 次
                </TableCell>
                <TableCell className="pr-3 text-right align-middle">
                  <ResourceAction
                    projectId={projectId}
                    resource={resource}
                    completed={stats.completed}
                  />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </Card>
  )
}

export const LearningEvaluationPage = ({
  projectId,
}: {
  projectId: string
}) => {
  const result = useAtomValue(learningEvaluationAtom(projectId))
  const [view, setView] = useState<View>('generated')

  const content = Result.builder(result)
    .onInitialOrWaiting(() => (
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-20 rounded-2xl" />
        ))}
      </div>
    ))
    .onFailure(() => (
      <Card className="border-destructive/40">
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          学习效果数据加载失败，请稍后重试。
        </CardContent>
      </Card>
    ))
    .onSuccess((evaluation) => {
      const incomplete = evaluation.resources.filter(
        (resource) => !getResourceStats(projectId, resource).completed,
      )
      const completed = evaluation.resources.filter(
        (resource) => getResourceStats(projectId, resource).completed,
      )
      const wrong = evaluation.resources.filter(
        (resource) => resource.wrongCount > 0,
      )
      const counts: Record<View, number> = {
        generated: evaluation.resources.length,
        incomplete: incomplete.length,
        completed: completed.length,
        wrong: wrong.length,
      }
      const resources =
        view === 'incomplete'
          ? incomplete
          : view === 'completed'
            ? completed
            : view === 'wrong'
              ? wrong
              : evaluation.resources

      return (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {(
              [
                ['generated', Layers3, 'text-[#021024]', 'bg-[#C1E8FF]/70'],
                ['incomplete', Clock3, 'text-[#052659]', 'bg-[#C1E8FF]/55'],
                [
                  'completed',
                  CheckCircle2,
                  'text-[#5483B3]',
                  'bg-[#C1E8FF]/40',
                ],
                ['wrong', CircleAlert, 'text-[#7DA0CA]', 'bg-[#C1E8FF]/25'],
              ] as const
            ).map(([key, Icon, color, background]) => (
              <button key={key} type="button" onClick={() => setView(key)}>
                <Card
                  className={cn(
                    'h-full rounded-2xl text-left transition-colors hover:border-primary/40',
                    view === key && 'border-primary ring-2 ring-primary/10',
                  )}
                >
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className={cn('rounded-xl p-3', color, background)}>
                      <Icon className="size-5" />
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">
                        {viewLabels[key]}
                      </div>
                      <div className="mt-1 text-3xl font-semibold">
                        {counts[key]}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </button>
            ))}
          </section>

          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">{viewLabels[view]}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                每次生成的题目作为一组展示，点击任意一行即可进入对应做题页面。
              </p>
            </div>

            {resources.length ? (
              <ResourceList projectId={projectId} resources={resources} />
            ) : (
              <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
                这里暂时没有{viewLabels[view]}的题目组。
              </div>
            )}
          </section>
        </>
      )
    })
    .render()

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <main className="container mx-auto max-w-7xl space-y-6 px-4 py-6">
          <Card className="rounded-[28px] border border-primary/15 bg-gradient-to-br from-[#C1E8FF]/60 via-white to-[#7DA0CA]/20 shadow-sm dark:from-[#052659] dark:via-background dark:to-[#5483B3]/30">
            <CardHeader className="p-6">
              <CardTitle className="text-2xl">学习效果评估</CardTitle>
              <p className="text-sm text-muted-foreground">
                基于资源包生成的测试题、闪卡及真实练习记录评估学习进度。
              </p>
            </CardHeader>
          </Card>
          {content}
        </main>
      </div>
    </div>
  )
}
