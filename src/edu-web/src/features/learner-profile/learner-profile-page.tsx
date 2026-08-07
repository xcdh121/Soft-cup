import { useMemo } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import {
  ActivityIcon,
  AlertCircleIcon,
  BookOpenIcon,
  DatabaseIcon,
  Loader2Icon,
  RefreshCwIcon,
  SparklesIcon,
  TargetIcon,
  TrendingDownIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { LearnerProfileField } from '@/data-acess/learner-profile'
import type { KnowledgeGraphNode } from '@/data-acess/knowledge-graph'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { currentUserAtom } from '@/data-acess/auth'
import { knowledgeGraphAtom } from '@/data-acess/knowledge-graph'
import {
  learnerProfileAtom,
  learnerProfileRevisionsAtom,
  refreshLearnerProfileAtom,
} from '@/data-acess/learner-profile'
import { practiceRecordsAtom } from '@/data-acess/practice'
import { ProjectHeader } from '@/features/project/components/project-header'
import { resolveAvatarUrl } from '@/lib/auth-client'

type ProfileFieldView = {
  key: string
  label: string
  value: string
  confidence: number
  status: string
  evidence: Array<Record<string, unknown>>
  updatedAt?: string
  hasValue: boolean
}

type DailyPractice = {
  key: string
  label: string
  attempts: number
  accuracy: number | null
}

const FIELD_LABELS: Record<string, string> = {
  major_background: '专业背景',
  education_level: '学历层次',
  current_course: '当前课程',
  learning_goal: '学习目标',
  knowledge_background: '知识基础',
  learning_progress: '学习进度',
  resource_preference: '资源偏好',
  cognitive_style: '认知风格',
  common_error_types: '常见错误',
  practical_ability: '实践能力',
  available_study_time: '可用学习时间',
  current_learning_state: '当前学习状态',
}

const FIELD_GROUPS = [
  {
    title: '基础背景',
    description: '描述当前学习所处的专业、课程与目标环境。',
    keys: [
      'major_background',
      'education_level',
      'current_course',
      'learning_goal',
    ],
  },
  {
    title: '学习能力',
    description: '结合知识状态和练习表现形成的动态判断。',
    keys: [
      'knowledge_background',
      'learning_progress',
      'common_error_types',
      'practical_ability',
    ],
  },
  {
    title: '偏好与状态',
    description: '影响学习资源选择和学习节奏的个体特征。',
    keys: [
      'resource_preference',
      'cognitive_style',
      'available_study_time',
      'current_learning_state',
    ],
  },
]

const STATUS_META: Record<
  string,
  { label: string; className: string; dotClassName: string }
> = {
  confirmed: {
    label: '已确认',
    className: 'border-[#5483B3] bg-[#C1E8FF]/50 text-[#052659]',
    dotClassName: 'bg-[#052659]',
  },
  inferred: {
    label: '系统推断',
    className: 'border-[#7DA0CA] bg-[#C1E8FF]/35 text-[#052659]',
    dotClassName: 'bg-[#5483B3]',
  },
  missing: {
    label: '待补充',
    className: 'border-[#C1E8FF] bg-[#C1E8FF]/20 text-[#5483B3]',
    dotClassName: 'bg-[#7DA0CA]',
  },
}

const SOURCE_LABELS: Record<string, string> = {
  project: '项目课程',
  practice_records: '练习记录',
  student_knowledge_states: '知识状态',
  chat_message: '学习对话',
  user_input: '学生填写',
  manual: '手动编辑',
}

const stringifyValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '待补充'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean')
    return String(value)

  if (Array.isArray(value)) {
    if (value.length === 0) return '暂无'
    return value
      .map((item) => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item !== null) {
          const record = item as Record<string, unknown>
          if ('topic' in record && 'count' in record) {
            return `${record.topic}（${record.count}次）`
          }
        }
        return JSON.stringify(item)
      })
      .join('、')
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>
    if ('accuracy' in record && 'attempt_count' in record) {
      return `练习 ${record.attempt_count} 次，正确率 ${Math.round(Number(record.accuracy) * 100)}%`
    }
    if ('average_mastery' in record && 'tracked_knowledge_points' in record) {
      const weakPoints = Array.isArray(record.weak_points)
        ? record.weak_points.join('、')
        : ''
      return `平均掌握度 ${record.average_mastery}%，追踪 ${record.tracked_knowledge_points} 个知识点${weakPoints ? `，薄弱点：${weakPoints}` : ''}`
    }
    return JSON.stringify(value)
  }

  return String(value)
}

const normalizeField = (key: string, raw: unknown): ProfileFieldView => {
  const maybeField =
    typeof raw === 'object' && raw !== null
      ? (raw as LearnerProfileField)
      : null
  const value = maybeField && 'value' in maybeField ? maybeField.value : raw
  const hasValue = !(
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  )
  const confidence =
    maybeField && typeof maybeField.confidence === 'number'
      ? maybeField.confidence
      : hasValue
        ? 0.5
        : 0

  return {
    key,
    label: FIELD_LABELS[key] ?? key,
    value: stringifyValue(value),
    confidence: Math.round(confidence * 100),
    status: maybeField?.status ?? (hasValue ? 'inferred' : 'missing'),
    evidence: Array.isArray(maybeField?.evidence) ? maybeField.evidence : [],
    updatedAt: maybeField?.updated_at,
    hasValue,
  }
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '暂无'
  return new Date(value).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const localDateKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

const MetricCard = ({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string
  value: string
  hint: string
  icon: ReactNode
  tone: string
}) => (
  <div className="relative overflow-hidden rounded-2xl border bg-card p-5 text-card-foreground shadow-sm">
    <div
      className={`absolute right-0 top-0 h-20 w-20 rounded-bl-[56px] ${tone}`}
    />
    <div className="relative flex items-start justify-between gap-4">
      <div>
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-2 text-3xl font-semibold tracking-tight">
          {value}
        </div>
        <div className="mt-2 text-xs text-muted-foreground">{hint}</div>
      </div>
      <div className="rounded-xl border bg-card p-2.5 text-card-foreground shadow-sm">
        {icon}
      </div>
    </div>
  </div>
)

const ChartEmpty = ({ children }: { children: ReactNode }) => (
  <div className="flex min-h-44 items-center justify-center rounded-xl border border-dashed bg-muted/20 px-6 text-center text-sm text-muted-foreground">
    {children}
  </div>
)

const PracticeTrendChart = ({ data }: { data: Array<DailyPractice> }) => {
  const activeDays = data.filter((item) => item.attempts > 0)
  if (activeDays.length === 0) {
    return (
      <ChartEmpty>完成练习后，这里会显示近 7 天正确率和练习量趋势。</ChartEmpty>
    )
  }

  const width = 680
  const chartLeft = 48
  const chartRight = 24
  const chartTop = 20
  const chartBottom = 168
  const xStep = (width - chartLeft - chartRight) / Math.max(1, data.length - 1)
  const maxAttempts = Math.max(...data.map((item) => item.attempts), 1)
  const pointFor = (item: DailyPractice, index: number) => ({
    x: chartLeft + index * xStep,
    y:
      item.accuracy === null
        ? null
        : chartBottom - (item.accuracy / 100) * (chartBottom - chartTop),
  })

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-[#5483B3]" />
          正确率
        </span>
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-[#C1E8FF]" />
          练习量
        </span>
      </div>
      <svg
        viewBox={`0 0 ${width} 230`}
        className="w-full overflow-visible"
        role="img"
        aria-label="近七天练习正确率与练习量趋势图"
      >
        {[0, 50, 100].map((tick) => {
          const y = chartBottom - (tick / 100) * (chartBottom - chartTop)
          return (
            <g key={tick}>
              <line
                x1={chartLeft}
                x2={width - chartRight}
                y1={y}
                y2={y}
                stroke="currentColor"
                className="text-border"
                strokeDasharray="4 5"
              />
              <text
                x={chartLeft - 10}
                y={y + 4}
                textAnchor="end"
                className="fill-muted-foreground text-[11px]"
              >
                {tick}%
              </text>
            </g>
          )
        })}

        {data.map((item, index) => {
          const point = pointFor(item, index)
          const nextPoint =
            index < data.length - 1
              ? pointFor(data[index + 1], index + 1)
              : null
          const barHeight = (item.attempts / maxAttempts) * 34
          return (
            <g key={item.key}>
              <rect
                x={point.x - 10}
                y={204 - barHeight}
                width="20"
                height={barHeight}
                rx="5"
                className="fill-[#C1E8FF]/80"
              />
              {point.y !== null && nextPoint && nextPoint.y !== null ? (
                <line
                  x1={point.x}
                  y1={point.y}
                  x2={nextPoint.x}
                  y2={nextPoint.y}
                  stroke="#5483b3"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              ) : null}
              {point.y !== null ? (
                <g>
                  <circle cx={point.x} cy={point.y} r="5" fill="#5483b3" />
                  <circle cx={point.x} cy={point.y} r="2" fill="white" />
                </g>
              ) : null}
              <text
                x={point.x}
                y="224"
                textAnchor="middle"
                className="fill-muted-foreground text-[11px]"
              >
                {item.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

const MasteryBars = ({ nodes }: { nodes: Array<KnowledgeGraphNode> }) => {
  const weakest = [...nodes]
    .sort((a, b) => a.mastery_score - b.mastery_score)
    .slice(0, 6)
  if (weakest.length === 0) {
    return (
      <ChartEmpty>知识状态生成后，这里会展示最需要巩固的知识点。</ChartEmpty>
    )
  }

  return (
    <div className="space-y-4">
      {weakest.map((node) => {
        const color =
          node.mastery_score < 40
            ? 'bg-[#021024]'
            : node.mastery_score < 60
              ? 'bg-[#052659]'
              : node.mastery_score < 80
                ? 'bg-[#5483B3]'
                : 'bg-[#7DA0CA]'
        return (
          <div key={node.id} className="space-y-1.5">
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="min-w-0 truncate font-medium" title={node.label}>
                {node.label}
              </span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {Math.round(node.mastery_score)}%
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${color}`}
                style={{ width: `${Math.max(2, node.mastery_score)}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

const Donut = ({
  value,
  label,
  gradient,
}: {
  value: string
  label: string
  gradient: string
}) => (
  <div
    className="relative mx-auto grid size-36 place-items-center rounded-full"
    style={{ background: gradient }}
  >
    <div className="grid size-24 place-items-center rounded-full border bg-background text-center shadow-inner">
      <div>
        <div className="text-2xl font-semibold">{value}</div>
        <div className="text-[11px] text-muted-foreground">{label}</div>
      </div>
    </div>
  </div>
)

const ProfileFieldRow = ({ field }: { field: ProfileFieldView }) => {
  const status = STATUS_META[field.status] ?? STATUS_META.inferred
  return (
    <div className="grid gap-3 border-b px-4 py-3 last:border-b-0 hover:bg-muted/20 md:grid-cols-[108px_minmax(0,1fr)_140px_104px] md:items-center">
      <div className="flex items-center justify-between gap-2 md:block">
        <div className="text-sm font-medium">{field.label}</div>
        <Badge variant="outline" className={status.className}>
          {status.label}
        </Badge>
      </div>
      <div
        className={`min-w-0 text-sm leading-5 ${field.hasValue ? 'text-foreground' : 'text-muted-foreground'}`}
      >
        {field.value}
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>可信度</span>
          <span>{field.confidence}%</span>
        </div>
        <Progress value={field.confidence} className="h-1.5" />
      </div>
      <div className="flex items-center justify-between gap-3 text-[11px] text-muted-foreground md:block md:text-right">
        <span>{field.evidence.length} 条证据</span>
        <span className="md:mt-1 md:block">
          {formatDateTime(field.updatedAt)}
        </span>
      </div>
    </div>
  )
}

export const LearnerProfilePage = ({ projectId }: { projectId: string }) => {
  const currentUserResult = useAtomValue(currentUserAtom)
  const profileResult = useAtomValue(learnerProfileAtom(projectId))
  const revisionsResult = useAtomValue(learnerProfileRevisionsAtom(projectId))
  const graphResult = useAtomValue(knowledgeGraphAtom(projectId))
  const practiceResult = useAtomValue(practiceRecordsAtom(projectId))
  const refreshProfile = useAtomSet(refreshLearnerProfileAtom, {
    mode: 'promise',
  })

  const currentUser = Result.isSuccess(currentUserResult)
    ? currentUserResult.value
    : null
  const profile = Result.isSuccess(profileResult) ? profileResult.value : null
  const revisions = Result.isSuccess(revisionsResult)
    ? revisionsResult.value
    : []
  const graph = Result.isSuccess(graphResult) ? graphResult.value : null
  const practiceRecords = Result.isSuccess(practiceResult)
    ? practiceResult.value
    : []
  const profileData = profile?.profile_data ?? {}

  const fields = useMemo(() => {
    const requiredKeys = FIELD_GROUPS.flatMap((group) => group.keys)
    const required = requiredKeys.map((key) =>
      normalizeField(key, profileData[key]),
    )
    const extra = Object.entries(profileData)
      .filter(([key]) => !requiredKeys.includes(key))
      .map(([key, value]) => normalizeField(key, value))
    return [...required, ...extra]
  }, [profileData])

  const completeness = Math.round((profile?.completeness_score ?? 0) * 100)
  const nodes = graph?.nodes ?? []
  const averageMastery = nodes.length
    ? Math.round(
        nodes.reduce((sum, node) => sum + node.mastery_score, 0) / nodes.length,
      )
    : null
  const weakNodes = nodes.filter((node) => node.mastery_score < 60)

  const dailyPractice = useMemo<Array<DailyPractice>>(() => {
    const days = Array.from({ length: 7 }, (_, index) => {
      const date = new Date()
      date.setHours(0, 0, 0, 0)
      date.setDate(date.getDate() - (6 - index))
      return {
        key: localDateKey(date),
        label: `${date.getMonth() + 1}/${date.getDate()}`,
        attempts: 0,
        correct: 0,
      }
    })
    const dayMap = new Map(days.map((day) => [day.key, day]))
    for (const record of practiceRecords) {
      const day = dayMap.get(localDateKey(new Date(record.created_at)))
      if (!day) continue
      day.attempts += 1
      if (record.was_correct) day.correct += 1
    }
    return days.map((day) => ({
      key: day.key,
      label: day.label,
      attempts: day.attempts,
      accuracy: day.attempts
        ? Math.round((day.correct / day.attempts) * 100)
        : null,
    }))
  }, [practiceRecords])

  const recentAttempts = dailyPractice.reduce(
    (sum, item) => sum + item.attempts,
    0,
  )
  const recentDayKeys = new Set(dailyPractice.map((item) => item.key))
  const recentCorrect = practiceRecords.filter(
    (record) =>
      recentDayKeys.has(localDateKey(new Date(record.created_at))) &&
      record.was_correct,
  ).length
  const recentAccuracy = recentAttempts
    ? Math.round((recentCorrect / recentAttempts) * 100)
    : null

  const errorTopics = useMemo(() => {
    const counts = new Map<string, number>()
    for (const record of practiceRecords) {
      if (!record.was_correct) {
        counts.set(record.topic, (counts.get(record.topic) ?? 0) + 1)
      }
    }
    return [...counts.entries()]
      .map(([topic, count]) => ({ topic, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
  }, [practiceRecords])

  const statusCounts = fields.reduce(
    (counts, field) => {
      const status = field.hasValue ? field.status : 'missing'
      if (status === 'confirmed') counts.confirmed += 1
      else if (status === 'missing') counts.missing += 1
      else counts.inferred += 1
      return counts
    },
    { confirmed: 0, inferred: 0, missing: 0 },
  )
  const statusTotal = Math.max(fields.length, 1)
  const confirmedEnd = (statusCounts.confirmed / statusTotal) * 100
  const inferredEnd =
    ((statusCounts.confirmed + statusCounts.inferred) / statusTotal) * 100

  const masteryBuckets = [
    {
      label: '需补基础',
      count: nodes.filter((node) => node.mastery_score < 40).length,
      color: '#021024',
    },
    {
      label: '需要巩固',
      count: nodes.filter(
        (node) => node.mastery_score >= 40 && node.mastery_score < 60,
      ).length,
      color: '#052659',
    },
    {
      label: '基本掌握',
      count: nodes.filter(
        (node) => node.mastery_score >= 60 && node.mastery_score < 80,
      ).length,
      color: '#5483b3',
    },
    {
      label: '掌握良好',
      count: nodes.filter((node) => node.mastery_score >= 80).length,
      color: '#7da0ca',
    },
  ]
  let masteryCursor = 0
  const masteryGradient = nodes.length
    ? `conic-gradient(${masteryBuckets
        .map((bucket) => {
          const start = masteryCursor
          masteryCursor += (bucket.count / nodes.length) * 100
          return `${bucket.color} ${start}% ${masteryCursor}%`
        })
        .join(', ')})`
    : 'conic-gradient(var(--muted) 0 100%)'

  const evidenceCounts = fields.reduce<Record<string, number>>(
    (counts, field) => {
      for (const evidence of field.evidence) {
        const source = String(evidence.source_type ?? 'other')
        const amount = Number(evidence.count ?? 1)
        counts[source] =
          (counts[source] ?? 0) + (Number.isFinite(amount) ? amount : 1)
      }
      return counts
    },
    {},
  )
  const evidenceSources = Object.entries(evidenceCounts)
    .map(([source, count]) => ({ source, count }))
    .sort((a, b) => b.count - a.count)
  const maxEvidence = Math.max(...evidenceSources.map((item) => item.count), 1)

  const summaryTags = fields
    .filter((field) => field.hasValue)
    .slice(0, 4)
    .map((field) => field.label)

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="relative overflow-hidden rounded-[30px] border border-primary/15 bg-gradient-to-br from-[#C1E8FF]/60 via-white to-[#7DA0CA]/20 p-6 shadow-sm dark:from-[#052659] dark:via-background dark:to-[#5483B3]/30">
            <div className="absolute -right-16 -top-24 size-64 rounded-full bg-[#7DA0CA]/30 blur-3xl" />
            <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                <Avatar className="size-20 border-4 border-white shadow-md">
                  <AvatarImage
                    src={resolveAvatarUrl(currentUser?.avatar_url)}
                    alt={currentUser ? `${currentUser.name}的头像` : '学生头像'}
                    className="object-cover"
                  />
                  <AvatarFallback className="bg-[#052659] text-xl font-semibold text-white">
                    {currentUser?.initials ?? '学生'}
                  </AvatarFallback>
                </Avatar>
                <div className="space-y-2">
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                      学生画像
                    </h1>
                    <p className="text-sm text-muted-foreground">
                      基于学习表现、知识状态和行为证据形成的动态学习分析。
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(summaryTags.length ? summaryTags : ['等待画像生成']).map(
                      (tag) => (
                        <Badge
                          key={tag}
                          variant="secondary"
                          className="rounded-full px-3 py-1"
                        >
                          {tag}
                        </Badge>
                      ),
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 md:justify-end">
                <div className="text-right text-xs text-muted-foreground">
                  <div>最近刷新</div>
                  <div className="mt-1 font-medium text-foreground">
                    {formatDateTime(profile?.last_refreshed_at)}
                  </div>
                </div>
                <Button onClick={() => refreshProfile(projectId)}>
                  <RefreshCwIcon className="size-4" />
                  刷新画像
                </Button>
              </div>
            </div>
            {profile ? (
              <div className="relative mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="画像完整度"
                  value={`${completeness}%`}
                  hint={`${statusCounts.missing} 个维度仍待补充`}
                  icon={<DatabaseIcon className="size-5 text-[#021024]" />}
                  tone="bg-[#C1E8FF]/70"
                />
                <MetricCard
                  label="平均知识掌握度"
                  value={
                    averageMastery === null ? '暂无' : `${averageMastery}%`
                  }
                  hint={`已追踪 ${nodes.length} 个知识点`}
                  icon={<BookOpenIcon className="size-5 text-[#052659]" />}
                  tone="bg-[#C1E8FF]/60"
                />
                <MetricCard
                  label="近 7 天正确率"
                  value={
                    recentAccuracy === null ? '暂无' : `${recentAccuracy}%`
                  }
                  hint={`共完成 ${recentAttempts} 次练习`}
                  icon={<ActivityIcon className="size-5 text-[#5483B3]" />}
                  tone="bg-[#C1E8FF]/50"
                />
                <MetricCard
                  label="薄弱知识点"
                  value={`${weakNodes.length}`}
                  hint="掌握度低于 60%"
                  icon={<TargetIcon className="size-5 text-[#7DA0CA]" />}
                  tone="bg-[#C1E8FF]/40"
                />
              </div>
            ) : null}
          </section>

          {!Result.isSuccess(profileResult) &&
          !Result.isFailure(profileResult) ? (
            <section className="rounded-[24px] border bg-card p-8 text-center text-card-foreground shadow-sm">
              <Loader2Icon className="mx-auto size-8 animate-spin text-muted-foreground" />
              <div className="mt-3 text-sm text-muted-foreground">
                正在加载学生画像...
              </div>
            </section>
          ) : profile ? (
            <>
              <section className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                <div className="mb-6">
                  <h2 className="text-lg font-semibold">十二维学生画像</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    可信度只表示判断可靠程度，不等同于学生能力得分。
                  </p>
                </div>
                <div className="space-y-4">
                  {FIELD_GROUPS.map((group) => (
                    <div
                      key={group.title}
                      className="overflow-hidden rounded-xl border"
                    >
                      <div className="border-b bg-muted/30 px-4 py-3">
                        <h3 className="text-sm font-semibold">{group.title}</h3>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {group.description}
                        </p>
                      </div>
                      <div>
                        {group.keys.map((key) => (
                          <ProfileFieldRow
                            key={key}
                            field={fields.find((field) => field.key === key)!}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <div className="mb-5 flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-lg font-semibold">近 7 天练习趋势</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        正确率来自实际答题记录，柱形表示每天的练习量。
                      </p>
                    </div>
                    <Badge variant="outline">{recentAttempts} 次练习</Badge>
                  </div>
                  <PracticeTrendChart data={dailyPractice} />
                </div>

                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <div>
                    <h2 className="text-lg font-semibold">知识掌握分布</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      基于当前知识状态，而非画像可信度。
                    </p>
                  </div>
                  <div className="mt-6 grid gap-6 sm:grid-cols-[160px_1fr] sm:items-center xl:grid-cols-1">
                    <Donut
                      value={
                        averageMastery === null ? '--' : `${averageMastery}%`
                      }
                      label="平均掌握度"
                      gradient={masteryGradient}
                    />
                    <div className="grid grid-cols-2 gap-3">
                      {masteryBuckets.map((bucket) => (
                        <div
                          key={bucket.label}
                          className="rounded-xl bg-muted/35 p-3"
                        >
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span
                              className="size-2 rounded-full"
                              style={{ backgroundColor: bucket.color }}
                            />
                            {bucket.label}
                          </div>
                          <div className="mt-1 text-lg font-semibold">
                            {bucket.count}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <div className="mb-5 flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-lg font-semibold">优先巩固知识点</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        按掌握度从低到高排列，优先处理高风险薄弱点。
                      </p>
                    </div>
                    <TrendingDownIcon className="size-5 text-[#052659]" />
                  </div>
                  <MasteryBars nodes={nodes} />
                </div>

                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <div className="mb-5">
                    <h2 className="text-lg font-semibold">高频错误主题</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      汇总全部练习记录，定位最常出现错误的内容。
                    </p>
                  </div>
                  {errorTopics.length ? (
                    <div className="space-y-4">
                      {errorTopics.map((item, index) => (
                        <div
                          key={item.topic}
                          className="grid grid-cols-[24px_1fr_auto] items-center gap-3"
                        >
                          <div className="text-center text-xs font-semibold text-muted-foreground">
                            {index + 1}
                          </div>
                          <div className="min-w-0">
                            <div
                              className="truncate text-sm font-medium"
                              title={item.topic}
                            >
                              {item.topic}
                            </div>
                            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-[#7DA0CA] to-[#052659]"
                                style={{
                                  width: `${(item.count / errorTopics[0].count) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                          <div className="text-sm font-semibold tabular-nums">
                            {item.count} 次
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <ChartEmpty>目前没有错误练习记录，继续保持。</ChartEmpty>
                  )}
                </div>
              </section>

              <section className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <h2 className="text-lg font-semibold">画像状态</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    区分已确认信息、系统推断和待补充字段。
                  </p>
                  <div className="mt-6 grid gap-6 sm:grid-cols-[160px_1fr] sm:items-center xl:grid-cols-1">
                    <Donut
                      value={`${fields.length - statusCounts.missing}/${fields.length}`}
                      label="已具备画像"
                      gradient={`conic-gradient(#052659 0 ${confirmedEnd}%, #5483b3 ${confirmedEnd}% ${inferredEnd}%, #c1e8ff ${inferredEnd}% 100%)`}
                    />
                    <div className="space-y-3">
                      {Object.entries(statusCounts).map(([key, count]) => {
                        const meta = STATUS_META[key]
                        return (
                          <div
                            key={key}
                            className="flex items-center justify-between rounded-xl bg-muted/35 px-3 py-2 text-sm"
                          >
                            <span className="flex items-center gap-2">
                              <span
                                className={`size-2 rounded-full ${meta.dotClassName}`}
                              />
                              {meta.label}
                            </span>
                            <span className="font-semibold">{count}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>

                <div className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                  <h2 className="text-lg font-semibold">画像证据来源</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    展示当前画像判断主要建立在哪些数据上。
                  </p>
                  <div className="mt-5 space-y-4">
                    {evidenceSources.length ? (
                      evidenceSources.map((item) => (
                        <div key={item.source}>
                          <div className="flex items-center justify-between text-sm">
                            <span>
                              {SOURCE_LABELS[item.source] ?? item.source}
                            </span>
                            <span className="font-semibold">{item.count}</span>
                          </div>
                          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-[#5483B3]"
                              style={{
                                width: `${(item.count / maxEvidence) * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        暂无可展示的画像证据。
                      </div>
                    )}
                  </div>
                </div>
              </section>

              <section className="rounded-[24px] border bg-card p-6 text-card-foreground shadow-sm">
                <div className="mb-5">
                  <h2 className="text-lg font-semibold">画像变化时间轴</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    说明画像在何时、因为什么证据发生变化。
                  </p>
                </div>
                {revisions.length ? (
                  <div className="relative ml-2 space-y-5 border-l pl-6">
                    {revisions.slice(0, 8).map((revision) => (
                      <div key={revision.id} className="relative">
                        <span className="absolute -left-[31px] top-1 size-3 rounded-full border-2 border-background bg-primary" />
                        <div className="flex flex-col gap-2 rounded-2xl bg-muted/35 p-4 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium">
                                {FIELD_LABELS[revision.field_key] ??
                                  revision.field_key}
                              </span>
                              <Badge variant="secondary">
                                {SOURCE_LABELS[revision.source_type] ??
                                  revision.source_type}
                              </Badge>
                            </div>
                            <div className="mt-2 text-sm text-muted-foreground">
                              <span className="line-through opacity-70">
                                {stringifyValue(revision.old_value)}
                              </span>
                              <span className="mx-2">→</span>
                              <span className="font-medium text-foreground">
                                {stringifyValue(revision.new_value)}
                              </span>
                            </div>
                          </div>
                          <div className="shrink-0 text-xs text-muted-foreground">
                            {formatDateTime(revision.created_at)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <ChartEmpty>暂无画像变更记录。</ChartEmpty>
                )}
              </section>
            </>
          ) : Result.isSuccess(profileResult) ? (
            <section className="rounded-[24px] border bg-card p-8 text-center text-card-foreground shadow-sm">
              <SparklesIcon className="mx-auto size-9 text-[#5483B3]" />
              <h2 className="mt-4 text-lg font-semibold">还没有学生画像</h2>
              <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
                点击生成后，系统会从当前项目的课程、练习记录和知识状态中自动生成初版画像。
              </p>
              <Button
                className="mt-5"
                onClick={() => refreshProfile(projectId)}
              >
                <RefreshCwIcon className="size-4" />
                生成学生画像
              </Button>
            </section>
          ) : null}

          {Result.isFailure(profileResult) ? (
            <section className="rounded-[20px] border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              <div className="flex items-center gap-2">
                <AlertCircleIcon className="size-4" />
                <span>画像加载失败，请确认后端服务已经启动。</span>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  )
}
