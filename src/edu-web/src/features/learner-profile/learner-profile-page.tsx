import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import {
  AlertCircleIcon,
  Loader2Icon,
  RefreshCwIcon,
  SparklesIcon,
} from 'lucide-react'
import type { LearnerProfileField } from '@/data-acess/learner-profile'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  learnerProfileAtom,
  learnerProfileRevisionsAtom,
  refreshLearnerProfileAtom,
} from '@/data-acess/learner-profile'
import { ProjectHeader } from '@/features/project/components/project-header'

type ProfileFieldView = {
  key: string
  label: string
  value: string
  confidence: number
  status: string
  updatedAt?: string
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

const colorClasses = [
  'bg-sky-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-violet-500',
  'bg-cyan-500',
]

const RADAR_DIMENSIONS = [
  { key: 'knowledge_background', label: '知识基础' },
  { key: 'learning_progress', label: '学习进度' },
  { key: 'cognitive_style', label: '认知能力' },
  { key: 'practical_ability', label: '实践能力' },
  { key: 'current_learning_state', label: '学习状态' },
]

const StudentRadar = ({
  values,
}: {
  values: Array<{ label: string; value: number }>
}) => {
  const center = 150
  const radius = 86
  const point = (index: number, scale = 1) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / values.length
    return `${center + Math.cos(angle) * radius * scale},${center + Math.sin(angle) * radius * scale}`
  }

  return (
    <svg
      viewBox="0 0 300 280"
      className="mx-auto mt-2 w-full max-w-[320px]"
      role="img"
      aria-label="学生五维能力雷达图"
    >
      {[0.25, 0.5, 0.75, 1].map((scale) => (
        <polygon
          key={scale}
          points={values.map((_, index) => point(index, scale)).join(' ')}
          fill="none"
          stroke="currentColor"
          className="text-slate-200"
        />
      ))}
      {values.map((_, index) => {
        const [x, y] = point(index).split(',')
        return (
          <line
            key={index}
            x1={center}
            y1={center}
            x2={x}
            y2={y}
            stroke="currentColor"
            className="text-slate-200"
          />
        )
      })}
      <polygon
        points={values
          .map((item, index) => point(index, item.value / 100))
          .join(' ')}
        fill="rgba(14, 165, 233, 0.22)"
        stroke="#0ea5e9"
        strokeWidth="2.5"
      />
      {values.map((item, index) => {
        const [x, y] = point(index, 1.25).split(',').map(Number)
        const [dotX, dotY] = point(index, item.value / 100)
          .split(',')
          .map(Number)
        return (
          <g key={item.label}>
            <circle cx={dotX} cy={dotY} r="4" fill="#0ea5e9" />
            <text
              x={x}
              y={y - 4}
              textAnchor="middle"
              className="fill-foreground text-[11px] font-medium"
            >
              {item.label}
            </text>
            <text
              x={x}
              y={y + 11}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {item.value}%
            </text>
          </g>
        )
      })}
    </svg>
  )
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
    typeof raw === 'object' && raw !== null ? (raw as LearnerProfileField) : null
  const value = maybeField && 'value' in maybeField ? maybeField.value : raw
  const confidence =
    maybeField && typeof maybeField.confidence === 'number'
      ? maybeField.confidence
      : value
        ? 0.5
        : 0

  return {
    key,
    label: FIELD_LABELS[key] ?? key,
    value: stringifyValue(value),
    confidence: Math.round(confidence * 100),
    status: maybeField?.status ?? 'missing',
    updatedAt: maybeField?.updated_at,
  }
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '暂无'
  return new Date(value).toLocaleString()
}

export const LearnerProfilePage = ({ projectId }: { projectId: string }) => {
  const profileResult = useAtomValue(learnerProfileAtom(projectId))
  const revisionsResult = useAtomValue(learnerProfileRevisionsAtom(projectId))
  const refreshProfile = useAtomSet(refreshLearnerProfileAtom, {
    mode: 'promise',
  })

  const profile = Result.isSuccess(profileResult) ? profileResult.value : null
  const revisions = Result.isSuccess(revisionsResult) ? revisionsResult.value : []
  const profileData = profile?.profile_data ?? {}
  const fields = profile
    ? Object.entries(profileData).map(([key, value]) =>
        normalizeField(key, value),
      )
    : []
  const completeness = Math.round((profile?.completeness_score ?? 0) * 100)
  const summaryTags = fields
    .filter((field) => field.value !== '待补充')
    .slice(0, 4)
    .map((field) => field.label)
  const radarValues = RADAR_DIMENSIONS.map((dimension) => ({
    label: dimension.label,
    value:
      fields.find((field) => field.key === dimension.key)?.confidence ?? 0,
  }))
  const weakestDimensions = [...radarValues]
    .sort((a, b) => a.value - b.value)
    .slice(0, 2)

  const handleRefresh = () => {
    refreshProfile(projectId)
  }

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-6xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="rounded-[30px] border bg-gradient-to-br from-slate-50 via-white to-amber-50 p-6 shadow-sm">
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                <Avatar className="size-20 border-4 border-white shadow-md">
                  <AvatarFallback className="bg-slate-900 text-xl font-semibold text-white">
                    学生
                  </AvatarFallback>
                </Avatar>

                <div className="space-y-2">
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                      学生画像
                    </h1>
                    <p className="text-sm text-muted-foreground">
                      汇总当前项目中的学习表现、能力倾向与内容偏好。
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(summaryTags.length > 0
                      ? summaryTags
                      : ['等待画像生成']
                    ).map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="rounded-full px-3 py-1"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 md:items-end">
                <div className="rounded-2xl bg-white/80 px-4 py-3 text-sm text-muted-foreground shadow-sm ring-1 ring-black/5">
                  画像完整度
                  <div className="mt-1 text-2xl font-semibold text-foreground">
                    {completeness}%
                  </div>
                  <div className="mt-1 text-xs">
                    最近刷新：{formatDateTime(profile?.last_refreshed_at)}
                  </div>
                </div>
                <Button onClick={handleRefresh}>
                  <RefreshCwIcon className="mr-2 size-4" />
                  刷新画像
                </Button>
              </div>
            </div>
          </section>

          {!Result.isSuccess(profileResult) ? (
            <section className="rounded-[24px] border bg-background p-8 text-center shadow-sm">
              <Loader2Icon className="mx-auto size-8 animate-spin text-muted-foreground" />
              <div className="mt-3 text-sm text-muted-foreground">
                正在加载学生画像...
              </div>
            </section>
          ) : profile ? (
            <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-[24px] border bg-background p-6 shadow-sm">
                <div className="mb-5">
                  <h2 className="text-lg font-semibold">学生特点</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    不同颜色表示不同学生特点，柱状长度表示画像可信度。
                  </p>
                </div>

                <div className="space-y-5">
                  {fields.length > 0 ? (
                    fields.map((field, index) => (
                      <div key={field.key} className="space-y-2">
                        <div className="flex items-end justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2 text-sm font-medium">
                              <span>{field.label}</span>
                              <Badge variant="outline" className="text-[10px]">
                                {field.status}
                              </Badge>
                            </div>
                            <div className="mt-1 text-xs leading-5 text-muted-foreground">
                              {field.value}
                            </div>
                          </div>
                          <div className="text-sm font-semibold">
                            {field.confidence}%
                          </div>
                        </div>

                        <div className="h-4 rounded-full bg-muted/70">
                          <div
                            className={`h-4 rounded-full ${colorClasses[index % colorClasses.length]} transition-all`}
                            style={{ width: `${field.confidence}%` }}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl bg-muted/40 p-5 text-sm text-muted-foreground">
                      当前画像还没有字段。点击“刷新画像”后，系统会根据课程、
                      练习记录和知识状态生成初版画像。
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-6">
                <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">五维能力雷达图</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    从五个核心维度观察学生的综合学习状态。
                  </p>
                  <StudentRadar values={radarValues} />
                </section>

                <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">画像解读</h2>
                  <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                    {weakestDimensions[0]?.value === 0 ? (
                      <p>
                        当前画像证据仍不完整，建议先补充学习记录，以便准确判断薄弱方面。
                      </p>
                    ) : (
                      <p>
                        学生目前在
                        <span className="font-semibold text-foreground">
                          {weakestDimensions.map((item) => item.label).join('、')}
                        </span>
                        方面较为薄弱，其中{weakestDimensions[0].label}得分最低（
                        {weakestDimensions[0].value}%）。建议优先安排该方向的针对性学习与练习。
                      </p>
                    )}
                  </div>
                </section>

                <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">最近变更</h2>
                  <div className="mt-4 space-y-3">
                    {revisions.slice(0, 5).map((revision) => (
                      <div key={revision.id} className="rounded-2xl bg-muted/40 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium">
                            {FIELD_LABELS[revision.field_key] ?? revision.field_key}
                          </div>
                          <Badge variant="secondary">{revision.source_type}</Badge>
                        </div>
                        <div className="mt-2 text-sm text-muted-foreground">
                          更新为：{stringifyValue(revision.new_value)}
                        </div>
                        <div className="mt-2 text-xs text-muted-foreground">
                          {formatDateTime(revision.created_at)}
                        </div>
                      </div>
                    ))}

                    {revisions.length === 0 ? (
                      <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
                        暂无画像变更记录。
                      </div>
                    ) : null}
                  </div>
                </section>
              </div>
            </section>
          ) : (
            <section className="rounded-[24px] border bg-background p-8 text-center shadow-sm">
              <SparklesIcon className="mx-auto size-9 text-amber-500" />
              <h2 className="mt-4 text-lg font-semibold">还没有学生画像</h2>
              <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
                点击刷新后，系统会从当前项目的课程、练习记录和知识状态中
                自动生成初版画像。
              </p>
              <Button className="mt-5" onClick={handleRefresh}>
                <RefreshCwIcon className="mr-2 size-4" />
                生成学生画像
              </Button>
            </section>
          )}

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
