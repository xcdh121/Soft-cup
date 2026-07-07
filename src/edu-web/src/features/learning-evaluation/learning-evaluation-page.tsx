import { useState } from 'react'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Layers3,
} from 'lucide-react'
import type { EvaluationResource } from '@/data-acess/learning-evaluation'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
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

const ResourceCard = ({
  projectId,
  resource,
}: {
  projectId: string
  resource: EvaluationResource
}) => {
  const progress = resource.itemCount
    ? Math.round((resource.answeredCount / resource.itemCount) * 100)
    : 0
  const to =
    resource.type === 'quiz'
      ? '/dashboard/p/$projectId/q/$quizId'
      : '/dashboard/p/$projectId/f/$flashcardGroupId'
  const params =
    resource.type === 'quiz'
      ? { projectId, quizId: resource.id }
      : { projectId, flashcardGroupId: resource.id }

  return (
    <Card className="rounded-2xl">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 gap-3">
            <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
              {resource.type === 'quiz' ? (
                <BookOpenCheck className="size-5" />
              ) : (
                <BrainCircuit className="size-5" />
              )}
            </div>
            <div className="min-w-0">
              <div className="truncate font-medium">{resource.name}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {resource.type === 'quiz' ? '测试题' : '闪卡'} ·{' '}
                {resource.itemCount} 项
              </div>
            </div>
          </div>
          <Badge variant={resource.status === 'completed' ? 'default' : 'secondary'}>
            {resource.status === 'completed' ? '已完成' : '未完成'}
          </Badge>
        </div>

        <div>
          <div className="mb-2 flex justify-between text-xs text-muted-foreground">
            <span>学习进度</span>
            <span>
              {resource.answeredCount}/{resource.itemCount}
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            错误作答 {resource.wrongCount} 次
          </span>
          <Button size="sm" asChild>
            <Link to={to} params={params as never}>
              {resource.status === 'completed' ? '再次练习' : '继续学习'}
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export const LearningEvaluationPage = ({ projectId }: { projectId: string }) => {
  const result = useAtomValue(learningEvaluationAtom(projectId))
  const [view, setView] = useState<View>('generated')

  const content = Result.builder(result)
    .onInitialOrWaiting(() => (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-48 rounded-2xl" />
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
        (resource) => resource.status === 'incomplete',
      )
      const completed = evaluation.resources.filter(
        (resource) => resource.status === 'completed',
      )
      const counts: Record<View, number> = {
        generated: evaluation.resources.length,
        incomplete: incomplete.length,
        completed: completed.length,
        wrong: evaluation.wrongRecords.length,
      }
      const resources =
        view === 'incomplete'
          ? incomplete
          : view === 'completed'
            ? completed
            : evaluation.resources

      return (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {(
              [
                ['generated', Layers3, 'text-sky-600', 'bg-sky-50'],
                ['incomplete', Clock3, 'text-amber-600', 'bg-amber-50'],
                ['completed', CheckCircle2, 'text-emerald-600', 'bg-emerald-50'],
                ['wrong', CircleAlert, 'text-rose-600', 'bg-rose-50'],
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
                      <div className="mt-1 text-3xl font-semibold">{counts[key]}</div>
                    </div>
                  </CardContent>
                </Card>
              </button>
            ))}
          </section>

          <section>
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">{viewLabels[view]}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {view === 'wrong'
                    ? '汇总测试题与闪卡练习中的错误作答。'
                    : '完成资源中的全部题目或闪卡后，状态会自动更新。'}
                </p>
              </div>
            </div>

            {view === 'wrong' ? (
              evaluation.wrongRecords.length ? (
                <div className="space-y-3">
                  {evaluation.wrongRecords.map((record) => (
                    <Card key={record.id} className="rounded-2xl">
                      <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">
                              {record.itemType === 'quiz' ? '测试题' : '闪卡'}
                            </Badge>
                            <span className="truncate font-medium">{record.topic}</span>
                          </div>
                          <div className="mt-2 text-sm text-muted-foreground">
                            你的答案：{record.userAnswer || '未掌握'} · 正确答案：
                            {record.correctAnswer}
                          </div>
                        </div>
                        <div className="shrink-0 text-xs text-muted-foreground">
                          {new Date(record.createdAt).toLocaleString('zh-CN')}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
                  暂无错题记录。
                </div>
              )
            ) : resources.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {resources.map((resource) => (
                  <ResourceCard
                    key={`${resource.type}-${resource.id}`}
                    projectId={projectId}
                    resource={resource}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
                这里暂时没有{viewLabels[view]}的学习资源。
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
          <Card className="rounded-[28px] border-0 bg-gradient-to-br from-cyan-50 via-white to-lime-50 shadow-sm">
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
