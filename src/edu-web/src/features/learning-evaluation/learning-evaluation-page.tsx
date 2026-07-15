import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Layers3,
  ListChecks,
  Star,
  Trophy,
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
export type LearningEvaluationSection = 'history' | 'practice'

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

const getProgrammingGrades = (
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
      `programming-grades:${projectId}:${resource.id}`,
    )
    const parsed = value ? JSON.parse(value) : {}
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
      return []
    return Object.values(parsed as Record<string, { score?: unknown }>).flatMap(
      (grade) =>
        typeof grade.score === 'number' && Number.isFinite(grade.score)
          ? [grade.score]
          : [],
    )
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
  const programmingGrades = getProgrammingGrades(projectId, resource)
  const submittedCount = programmingGrades.length
  const completed =
    resource.type === 'programming_questions'
      ? resource.itemCount > 0 && submittedCount >= resource.itemCount
      : resource.status === 'completed'

  return {
    attemptCount:
      resource.type === 'programming_questions' ? submittedCount : attemptCount,
    accuracy:
      resource.type === 'programming_questions'
        ? programmingGrades.length
          ? Math.round(
              programmingGrades.reduce((sum, score) => sum + score, 0) /
                programmingGrades.length,
            )
          : null
        : attemptCount
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
  const label = completed ? '重做' : '去做题'
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
    <div className="overflow-hidden border bg-card shadow-sm">
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
                          starIndex < stars && 'fill-amber-400 text-amber-500',
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
                        {resource.type === 'programming_questions'
                          ? '(AI 平均分)'
                          : `(${resource.questions.reduce(
                              (sum, question) => sum + question.correctCount,
                              0,
                            )}/${resource.questions.reduce(
                              (sum, question) => sum + question.attemptCount,
                              0,
                            )})`}
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
    </div>
  )
}

const dateKey = (date: Date) =>
  [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')

type RadarMetric = { label: string; value: number }

const radarPoint = (
  index: number,
  value: number,
  count: number,
  radius = 92,
) => {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / count
  const distance = radius * (Math.max(0, Math.min(100, value)) / 100)
  return {
    x: 150 + Math.cos(angle) * distance,
    y: 150 + Math.sin(angle) * distance,
  }
}

const RadarChart = ({
  title,
  description,
  metrics,
  color,
}: {
  title: string
  description: string
  metrics: Array<RadarMetric>
  color: string
}) => {
  const safeMetrics = metrics.length >= 3 ? metrics : []
  if (!safeMetrics.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          完成更多练习后生成雷达图。
        </CardContent>
      </Card>
    )
  }

  const gridLevels = [25, 50, 75, 100]
  const polygon = safeMetrics
    .map((metric, index) => {
      const point = radarPoint(index, metric.value, safeMetrics.length)
      return `${point.x},${point.y}`
    })
    .join(' ')

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle className="text-lg">{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="grid items-center gap-4 pt-2 sm:grid-cols-[minmax(0,1fr)_180px]">
        <svg
          viewBox="0 0 300 300"
          className="mx-auto aspect-square w-full max-w-80"
          role="img"
          aria-label={title}
        >
          {gridLevels.map((level) => (
            <polygon
              key={level}
              points={safeMetrics
                .map((_, index) => {
                  const point = radarPoint(index, level, safeMetrics.length)
                  return `${point.x},${point.y}`
                })
                .join(' ')}
              fill="none"
              stroke="currentColor"
              strokeOpacity={level === 100 ? 0.22 : 0.1}
            />
          ))}
          {safeMetrics.map((metric, index) => {
            const end = radarPoint(index, 100, safeMetrics.length)
            const label = radarPoint(index, 100, safeMetrics.length, 116)
            return (
              <g key={metric.label}>
                <line
                  x1="150"
                  y1="150"
                  x2={end.x}
                  y2={end.y}
                  stroke="currentColor"
                  strokeOpacity="0.12"
                />
                <text
                  x={label.x}
                  y={label.y}
                  textAnchor={
                    Math.abs(label.x - 150) < 10
                      ? 'middle'
                      : label.x > 150
                        ? 'start'
                        : 'end'
                  }
                  dominantBaseline="middle"
                  className="fill-muted-foreground text-[10px]"
                >
                  {metric.label.slice(0, 8)}
                </text>
              </g>
            )
          })}
          <polygon
            points={polygon}
            fill={color}
            fillOpacity="0.2"
            stroke={color}
            strokeWidth="2.5"
          />
          {safeMetrics.map((metric, index) => {
            const point = radarPoint(index, metric.value, safeMetrics.length)
            return (
              <circle
                key={metric.label}
                cx={point.x}
                cy={point.y}
                r="3.5"
                fill={color}
              />
            )
          })}
        </svg>
        <div className="space-y-3">
          {safeMetrics.map((metric) => (
            <div key={metric.label}>
              <div className="mb-1 flex justify-between gap-2 text-xs">
                <span className="truncate text-muted-foreground">
                  {metric.label}
                </span>
                <span className="font-medium">{metric.value}%</span>
              </div>
              <Progress value={metric.value} className="h-1.5" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

const HistoryAnalysis = ({
  projectId,
  evaluation,
}: {
  projectId: string
  evaluation: {
    resources: Array<EvaluationResource>
    practiceRecords: Array<{
      id: string
      topic: string
      wasCorrect: boolean
      createdAt: string
    }>
    wrongRecords: Array<{ id: string; topic: string; createdAt: string }>
  }
}) => {
  const wrongCounts = new Map<string, number>()
  evaluation.wrongRecords.forEach((record) => {
    const topic = record.topic || '未分类题目'
    wrongCounts.set(topic, (wrongCounts.get(topic) ?? 0) + 1)
  })
  const wrongRanking = [...wrongCounts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)

  const knowledgeStats = new Map<
    string,
    { attempts: number; correct: number; wrong: number }
  >()
  evaluation.resources.forEach((resource) => {
    resource.questions.forEach((question) => {
      const points = question.knowledgePoints.length
        ? question.knowledgePoints
        : ['未标注知识点']
      points.forEach((point) => {
        const current = knowledgeStats.get(point) ?? {
          attempts: 0,
          correct: 0,
          wrong: 0,
        }
        current.attempts += question.attemptCount
        current.correct += question.correctCount
        current.wrong += question.wrongCount
        knowledgeStats.set(point, current)
      })
    })
  })
  const weakRanking = [...knowledgeStats.entries()]
    .filter(([, stats]) => stats.attempts > 0)
    .map(([name, stats]) => ({
      name,
      accuracy: Math.round((stats.correct / stats.attempts) * 100),
      wrong: stats.wrong,
    }))
    .sort((a, b) => a.accuracy - b.accuracy || b.wrong - a.wrong)
    .slice(0, 5)

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const sevenDays = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today)
    date.setDate(today.getDate() - (6 - index))
    const key = dateKey(date)
    const records = evaluation.practiceRecords.filter(
      (record) => dateKey(new Date(record.createdAt)) === key,
    )
    return {
      key,
      label: `${date.getMonth() + 1}/${date.getDate()}`,
      correct: records.filter((record) => record.wasCorrect).length,
      wrong: records.filter((record) => !record.wasCorrect).length,
      total: records.length,
    }
  })
  const maxDailyTotal = Math.max(...sevenDays.map((day) => day.total), 1)
  const recentTotal = sevenDays.reduce((sum, day) => sum + day.total, 0)
  const recentWrong = sevenDays.reduce((sum, day) => sum + day.wrong, 0)
  const recentCorrect = recentTotal - recentWrong
  const recentAccuracy = recentTotal
    ? Math.round((recentCorrect / recentTotal) * 100)
    : 0
  const activeDays = sevenDays.filter((day) => day.total > 0).length
  const topWrong = wrongRanking.at(0)
  const weakest = weakRanking.at(0)
  const completedResources = evaluation.resources.filter(
    (resource) => resource.status === 'completed',
  ).length
  const completionRate = evaluation.resources.length
    ? Math.round((completedResources / evaluation.resources.length) * 100)
    : 0

  const knowledgeRadarSource = [...knowledgeStats.entries()]
    .filter(([, stats]) => stats.attempts > 0)
    .sort((a, b) => b[1].attempts - a[1].attempts)
    .slice(0, 6)
    .map(([label, stats]) => ({
      label,
      value: Math.round((stats.correct / stats.attempts) * 100),
    }))
  const knowledgeRadar =
    knowledgeRadarSource.length >= 3
      ? knowledgeRadarSource
      : [
          { label: '近期正确率', value: recentAccuracy },
          { label: '练习活跃度', value: Math.min(100, recentTotal * 8) },
          {
            label: '知识覆盖度',
            value: Math.min(100, knowledgeStats.size * 15),
          },
          { label: '练习稳定性', value: Math.round((activeDays / 7) * 100) },
          { label: '任务完成度', value: completionRate },
          {
            label: '纠错能力',
            value: recentTotal
              ? Math.round((recentCorrect / recentTotal) * 100)
              : 0,
          },
        ]
  const totalWrong = evaluation.wrongRecords.length
  const errorRadar = [
    {
      label: '近期错题率',
      value: recentTotal ? Math.round((recentWrong / recentTotal) * 100) : 0,
    },
    {
      label: '错题集中度',
      value:
        totalWrong && topWrong
          ? Math.round((topWrong.count / totalWrong) * 100)
          : 0,
    },
    { label: '知识薄弱度', value: weakest ? 100 - weakest.accuracy : 0 },
    { label: '练习中断度', value: Math.round(((7 - activeDays) / 7) * 100) },
    {
      label: '重复错误风险',
      value: totalWrong
        ? Math.min(100, Math.round((wrongRanking.length / totalWrong) * 35))
        : 0,
    },
    { label: '任务未完成度', value: 100 - completionRate },
  ]

  const aiRecommendations = [
    weakest
      ? `第一优先级：针对“${weakest.name}”安排 15-20 分钟概念复习，再完成 5 道由易到难的专项题；当前正确率 ${weakest.accuracy}%，先以提升到 70% 为短期目标。`
      : '第一优先级：先完成一组选择题建立学习基线，系统才能更准确地识别薄弱知识点。',
    topWrong
      ? `第二优先级：“${topWrong.name}”累计错 ${topWrong.count} 次，建议逐题记录错误原因，区分概念混淆、审题遗漏和算法步骤错误，避免只记正确答案。`
      : '第二优先级：每次练习后补充错因记录，并在 24 小时内进行第一次复习。',
    activeDays < 4
      ? `练习节奏偏松散，近七天仅 ${activeDays} 天有练习。建议改为每天 10-15 分钟的小步练习，至少保持每周 4 天。`
      : `练习节奏较稳定，近七天有 ${activeDays} 天保持练习；下一阶段应增加薄弱知识点的定向训练比例。`,
    recentTotal > 0
      ? `复盘策略：近期正确率 ${recentAccuracy}%。正确率低于 70% 时优先回看知识点与例题；达到 80% 后再增加综合题和编程题。`
      : '复盘策略：完成练习后按“当天、3 天后、7 天后”的节奏复做错题，检查是否真正掌握。',
  ]

  return (
    <div className="space-y-6">
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BrainCircuit className="size-5 text-primary" />
            AI 学情解析
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-base leading-8 text-foreground/80">
            {recentTotal > 0
              ? `近七天共练习 ${recentTotal} 次，答对 ${recentCorrect} 次、答错 ${recentWrong} 次，阶段正确率为 ${recentAccuracy}%。${
                  topWrong
                    ? `“${topWrong.name}”是当前错题最集中的主题，共出现 ${topWrong.count} 次。`
                    : ''
                }${
                  weakest
                    ? `建议优先复习“${weakest.name}”，当前正确率为 ${weakest.accuracy}%。`
                    : '继续完成题目后，系统会给出更具体的薄弱知识点建议。'
                }`
              : '近七天还没有练习记录。完成选择题或编程题后，这里会自动生成针对性的学习建议。'}
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {aiRecommendations.map((recommendation, index) => (
              <div
                key={recommendation}
                className="rounded-xl border bg-background/75 p-4"
              >
                <div className="mb-2 text-sm font-semibold text-primary">
                  建议 {index + 1}
                </div>
                <p className="text-sm leading-7 text-muted-foreground">
                  {recommendation}
                </p>
              </div>
            ))}
          </div>
          <Button asChild>
            <Link
              to="/dashboard/p/$projectId/learning-evaluation/practice"
              params={{ projectId }}
            >
              <ListChecks className="mr-2 size-4" />
              去做题
            </Link>
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 2xl:grid-cols-2">
        <RadarChart
          title="知识掌握雷达"
          description="数值越高代表该维度表现越好，用于观察知识能力是否均衡。"
          metrics={knowledgeRadar}
          color="#5483B3"
        />
        <RadarChart
          title="学习风险雷达"
          description="数值越高代表风险越突出，建议优先处理伸展最明显的维度。"
          metrics={errorRadar}
          color="#f97316"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <RankingCard
          title="错题数量排行榜"
          emptyText="暂无错题记录"
          rows={wrongRanking.map((item) => ({
            label: item.name,
            value: `${item.count} 题`,
            percent: topWrong ? (item.count / topWrong.count) * 100 : 0,
          }))}
        />
        <RankingCard
          title="薄弱知识点排行榜"
          emptyText="完成练习后生成薄弱知识点排行"
          rows={weakRanking.map((item) => ({
            label: item.name,
            value: `${item.accuracy}%`,
            percent: 100 - item.accuracy,
          }))}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">近七天练习趋势</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-[#5483B3]" />
              正确
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-[#C1E8FF]" />
              错误
            </span>
          </div>
          <div className="grid h-56 grid-cols-7 items-end gap-3 border-b px-2 pb-2">
            {sevenDays.map((day) => (
              <div
                key={day.key}
                className="flex h-full min-w-0 flex-col items-center justify-end gap-2"
              >
                <span className="text-xs font-medium">{day.total}</span>
                <div
                  className="flex min-h-1 w-full max-w-12 flex-col-reverse overflow-hidden rounded-t-md bg-muted"
                  style={{
                    height: `${Math.max(4, (day.total / maxDailyTotal) * 82)}%`,
                  }}
                  title={`${day.label}：正确 ${day.correct}，错误 ${day.wrong}`}
                >
                  {day.total > 0 ? (
                    <>
                      <div
                        className="bg-[#5483B3]"
                        style={{
                          height: `${(day.correct / day.total) * 100}%`,
                        }}
                      />
                      <div
                        className="bg-[#C1E8FF]"
                        style={{ height: `${(day.wrong / day.total) * 100}%` }}
                      />
                    </>
                  ) : null}
                </div>
                <span className="text-xs text-muted-foreground">
                  {day.label}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

const RankingCard = ({
  title,
  emptyText,
  rows,
}: {
  title: string
  emptyText: string
  rows: Array<{ label: string; value: string; percent: number }>
}) => (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-lg">
        <Trophy className="size-5 text-[#5483B3]" />
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>
      {rows.length ? (
        <ol className="space-y-4">
          {rows.map((row, index) => (
            <li key={row.label} className="space-y-2">
              <div className="flex items-center gap-3 text-sm">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 font-semibold text-primary">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1 truncate font-medium">
                  {row.label}
                </span>
                <span className="shrink-0 text-muted-foreground">
                  {row.value}
                </span>
              </div>
              <Progress value={row.percent} className="ml-10 h-1.5 w-auto" />
            </li>
          ))}
        </ol>
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {emptyText}
        </p>
      )}
    </CardContent>
  </Card>
)

const ExerciseResources = ({
  projectId,
  resources: sectionResources,
}: {
  projectId: string
  resources: Array<EvaluationResource>
}) => {
  const [view, setView] = useState<View>('generated')
  const incomplete = sectionResources.filter(
    (resource) => !getResourceStats(projectId, resource).completed,
  )
  const completed = sectionResources.filter(
    (resource) => getResourceStats(projectId, resource).completed,
  )
  const wrong = sectionResources.filter((resource) => {
    const stats = getResourceStats(projectId, resource)
    return (
      resource.wrongCount > 0 ||
      (resource.type === 'programming_questions' &&
        stats.accuracy !== null &&
        stats.accuracy < 60)
    )
  })
  const counts: Record<View, number> = {
    generated: sectionResources.length,
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
          : sectionResources

  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {(
          [
            [
              'generated',
              Layers3,
              '!border-blue-200 !bg-blue-50 dark:!border-blue-900 dark:!bg-blue-950/35',
              'bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-300',
              '!border-blue-500 ring-blue-500/15',
            ],
            [
              'incomplete',
              Clock3,
              '!border-orange-200 !bg-orange-50 dark:!border-orange-900 dark:!bg-orange-950/35',
              'bg-orange-100 text-orange-700 dark:bg-orange-900/60 dark:text-orange-300',
              '!border-orange-500 ring-orange-500/15',
            ],
            [
              'completed',
              CheckCircle2,
              '!border-emerald-200 !bg-emerald-50 dark:!border-emerald-900 dark:!bg-emerald-950/35',
              'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300',
              '!border-emerald-500 ring-emerald-500/15',
            ],
            [
              'wrong',
              CircleAlert,
              '!border-rose-200 !bg-rose-50 dark:!border-rose-900 dark:!bg-rose-950/35',
              'bg-rose-100 text-rose-700 dark:bg-rose-900/60 dark:text-rose-300',
              '!border-rose-500 ring-rose-500/15',
            ],
          ] as const
        ).map(([key, Icon, cardTone, iconTone, activeTone]) => (
          <button
            key={key}
            type="button"
            className="text-left"
            onClick={() => setView(key)}
          >
            <Card
              className={cn(
                'h-full gap-0 rounded-lg py-0 text-left shadow-none transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:shadow-sm',
                cardTone,
                view === key && ['ring-2', activeTone],
              )}
            >
              <CardContent className="flex items-center gap-3 p-3.5">
                <div className={cn('rounded-lg p-2', iconTone)}>
                  <Icon className="size-4.5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground">
                    {viewLabels[key]}
                  </div>
                  <div className="mt-0.5 text-xl font-semibold tabular-nums">
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
            点击题目组或“去做题”即可进入对应的作答页面。
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
    </div>
  )
}

const sectionMeta: Record<
  LearningEvaluationSection,
  { title: string; description: string }
> = {
  history: {
    title: '历史错题数据展示分析',
    description: '通过 AI 解析、错题排行和近七天练习趋势定位薄弱环节。',
  },
  practice: {
    title: '题目练习',
    description: '统一查看选择题和编程题的完成情况，并进入对应作答页面。',
  },
}

export const LearningEvaluationPage = ({
  projectId,
  section = 'history',
}: {
  projectId: string
  section?: LearningEvaluationSection
}) => {
  const result = useAtomValue(learningEvaluationAtom(projectId))
  const meta = sectionMeta[section]
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
    .onSuccess((evaluation) =>
      section === 'history' ? (
        <HistoryAnalysis projectId={projectId} evaluation={evaluation} />
      ) : (
        <ExerciseResources
          projectId={projectId}
          resources={evaluation.resources.filter(
            (resource) =>
              resource.type === 'quiz' ||
              resource.type === 'programming_questions',
          )}
        />
      ),
    )
    .render()

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <main className="container mx-auto max-w-7xl space-y-6 px-4 py-6">
          <header className="space-y-3">
            <nav
              className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground"
              aria-label="面包屑"
            >
              <Link
                to="/dashboard/p/$projectId"
                params={{ projectId }}
                className="transition-colors hover:text-foreground"
              >
                AI导师对话
              </Link>
              <ChevronRight className="size-4" />
              <span>学习效果评估</span>
              <ChevronRight className="size-4" />
              <span className="text-foreground">{meta.title}</span>
            </nav>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                {meta.title}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {meta.description}
              </p>
            </div>
          </header>
          {content}
        </main>
      </div>
    </div>
  )
}
