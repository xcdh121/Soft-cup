import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  ClipboardCheck,
  History,
  Loader2,
  PlayCircle,
  RotateCw,
  SkipForward,
  Sparkles,
  Target,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import type {
  InterventionOutcome,
  LearningRecommendation,
  RecommendationEventType,
  RecommendationInteraction,
} from '@/data-acess/learning-closed-loop'
import type { AdaptedStudyPlan } from '@/data-acess/study-plan'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  adjustLearningPathAtom,
  closedLoopOverviewAtom,
  diagnosisOverviewAtom,
  recordRecommendationFeedbackAtom,
} from '@/data-acess/learning-closed-loop'
import { activateLearningVerification } from '@/lib/learning-verification-context'

type RecommendationStage =
  | 'unseen'
  | 'seen'
  | 'clicked'
  | 'started'
  | 'completed'
  | 'skipped'

const stageOrder: Record<RecommendationStage, number> = {
  unseen: 0,
  seen: 1,
  clicked: 2,
  started: 3,
  completed: 4,
  skipped: 4,
}

export const getRecommendationStage = (
  interactions: Array<RecommendationInteraction>,
): RecommendationStage => {
  if (interactions.some((item) => item.event_type === 'completed')) {
    return 'completed'
  }
  if (
    interactions.some(
      (item) =>
        item.event_type === 'skipped' || item.event_type === 'dismissed',
    )
  ) {
    return 'skipped'
  }
  if (
    interactions.some(
      (item) =>
        item.event_type === 'started' || item.event_type === 'progressed',
    )
  ) {
    return 'started'
  }
  if (interactions.some((item) => item.event_type === 'clicked')) {
    return 'clicked'
  }
  if (interactions.some((item) => item.event_type === 'impression')) {
    return 'seen'
  }
  return 'unseen'
}

export type InterventionOutcomeGroup = {
  recommendationId: string
  latest: InterventionOutcome
  history: Array<InterventionOutcome>
}

export const groupInterventionOutcomes = (
  outcomes: Array<InterventionOutcome>,
): Array<InterventionOutcomeGroup> => {
  const grouped = new Map<string, Array<InterventionOutcome>>()

  outcomes.forEach((outcome) => {
    const existing = grouped.get(outcome.recommendation_id) ?? []
    existing.push(outcome)
    grouped.set(outcome.recommendation_id, existing)
  })

  return Array.from(grouped, ([recommendationId, recommendationOutcomes]) => {
    const sorted = [...recommendationOutcomes].sort(
      (left, right) =>
        Date.parse(right.evaluated_at) - Date.parse(left.evaluated_at),
    )
    return {
      recommendationId,
      latest: sorted[0],
      history: sorted.slice(1),
    }
  })
}

export const getAdjustedOutcomeIds = (plan: AdaptedStudyPlan) => {
  const ids = new Set(plan.raw_learning_path.adjust_trigger_ids ?? [])
  if (plan.raw_learning_path.adjust_trigger_id) {
    ids.add(plan.raw_learning_path.adjust_trigger_id)
  }
  return ids
}

const stageLabels: Record<RecommendationStage, string> = {
  unseen: '未查看',
  seen: '已展示',
  clicked: '已点击',
  started: '学习中',
  completed: '已完成',
  skipped: '已跳过',
}

const eventLabels: Record<RecommendationEventType, string> = {
  impression: '已展示',
  clicked: '已点击',
  started: '开始学习',
  progressed: '学习进度',
  completed: '完成学习',
  dismissed: '已忽略',
  skipped: '已跳过',
  rated: '已评分',
}

const recommendationTypeLabels: Record<string, string> = {
  quiz: '专项选择题',
  flashcard: '复习闪卡',
  flashcards: '复习闪卡',
  note: '巩固笔记',
  mind_map: '知识导图',
  practice: '专项练习',
  resource: '学习资源',
}

const legacyRecommendationText: Record<string, string> = {
  'Complete targeted weak-point practice': '完成薄弱知识点专项练习',
  'The related knowledge point has low mastery.': '相关知识点当前掌握度较低。',
  'An existing project resource is available.':
    '已匹配项目中的已有资源作为巩固材料。',
  'No matching generated resource is currently available.':
    '暂未找到匹配的已生成资源，建议先完成专项练习。',
  'A new resource was queued through the project generation services.':
    '系统已根据本次诊断单独创建并生成该学习资源。',
  'The resource targets an evidence-backed weak knowledge point.':
    '该资源针对有学习证据支持的薄弱知识点。',
  "The resource type matches the learner's saved resource preference.":
    '资源类型符合学习者已保存的偏好。',
}

const studentFacingText = (value: string) =>
  legacyRecommendationText[value.trim()] ?? value

const recommendationSourceLabel = (recommendation: LearningRecommendation) => {
  if (recommendation.reason_codes.includes('generation_queued')) {
    return `本次新生成 · ${recommendationTypeLabels[recommendation.recommendation_type] ?? '学习资源'}`
  }
  if (recommendation.reason_codes.includes('available_resource')) {
    return `已有资源兜底 · ${recommendationTypeLabels[recommendation.recommendation_type] ?? '学习资源'}`
  }
  return (
    recommendationTypeLabels[recommendation.recommendation_type] ?? '学习资源'
  )
}

const toNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

const percent = (value: number | null | undefined) =>
  value == null ? '—' : `${Math.round(value * 100)}%`

export type RecommendationResourceDestination =
  | 'quiz'
  | 'flashcards'
  | 'note'
  | 'mind_map'
  | 'practice'
  | 'resource_packages'

export const getRecommendationResourceDestination = (
  recommendationType: string,
  targetId: string | null | undefined,
): RecommendationResourceDestination => {
  if (targetId && recommendationType === 'quiz') return 'quiz'
  if (
    targetId &&
    (recommendationType === 'flashcard' || recommendationType === 'flashcards')
  ) {
    return 'flashcards'
  }
  if (targetId && recommendationType === 'note') return 'note'
  if (targetId && recommendationType === 'mind_map') return 'mind_map'
  if (recommendationType === 'practice') return 'practice'
  return 'resource_packages'
}

const RecommendationResourceLink = ({
  projectId,
  recommendation,
  onOpen,
}: {
  projectId: string
  recommendation: LearningRecommendation
  onOpen: () => void
}) => {
  const targetId = recommendation.target_id
  const type = recommendation.recommendation_type
  const destination = getRecommendationResourceDestination(type, targetId)
  if (destination === 'quiz') {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link
          to="/dashboard/p/$projectId/q/$quizId"
          params={{ projectId, quizId: targetId! }}
          onClick={onOpen}
        >
          打开推荐题目 <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    )
  }
  if (destination === 'flashcards') {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link
          to="/dashboard/p/$projectId/f/$flashcardGroupId"
          params={{ projectId, flashcardGroupId: targetId! }}
          onClick={onOpen}
        >
          打开推荐闪卡 <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    )
  }
  if (destination === 'note') {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link
          to="/dashboard/p/$projectId/n/$noteId"
          params={{ projectId, noteId: targetId! }}
          onClick={onOpen}
        >
          打开巩固笔记 <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    )
  }
  if (destination === 'mind_map') {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link
          to="/dashboard/p/$projectId/m/$mindMapId"
          params={{ projectId, mindMapId: targetId! }}
          onClick={onOpen}
        >
          打开知识导图 <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    )
  }
  if (destination === 'practice') {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link
          to="/dashboard/p/$projectId/learning-evaluation/practice"
          params={{ projectId }}
          onClick={onOpen}
        >
          开始专项练习 <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    )
  }
  return (
    <Button size="sm" variant="outline" asChild>
      <Link
        to="/dashboard/p/$projectId/resource-packages"
        params={{ projectId }}
        onClick={onOpen}
      >
        查看学习资源 <ArrowUpRight className="size-3.5" />
      </Link>
    </Button>
  )
}

export const StudyPlanRecommendationFeedback = ({
  projectId,
  plan,
}: {
  projectId: string
  plan: AdaptedStudyPlan
}) => {
  const overviewResult = useAtomValue(closedLoopOverviewAtom(projectId))
  const recordFeedback = useAtomSet(recordRecommendationFeedbackAtom, {
    mode: 'promise',
  })
  const impressionRequests = useRef(new Set<string>())
  const [pendingAction, setPendingAction] = useState<string | null>(null)
  const [ratings, setRatings] = useState<Record<string, string>>({})

  const overview = Result.isSuccess(overviewResult)
    ? overviewResult.value
    : null
  const recommendationIds = new Set(plan.based_on_recommendation_ids)
  const recommendations = (overview?.recommendations ?? []).filter((item) =>
    recommendationIds.has(item.id),
  )

  useEffect(() => {
    if (!overview) return
    for (const recommendation of recommendations) {
      const interactions =
        overview.interactionsByRecommendation[recommendation.id] ?? []
      if (
        interactions.some((item) => item.event_type === 'impression') ||
        impressionRequests.current.has(recommendation.id)
      ) {
        continue
      }
      impressionRequests.current.add(recommendation.id)
      void recordFeedback({
        projectId,
        recommendationId: recommendation.id,
        eventType: 'impression',
        resourceId: recommendation.target_id ?? undefined,
      }).catch(() => impressionRequests.current.delete(recommendation.id))
    }
  }, [overview, projectId, recommendations, recordFeedback])

  const submitFeedback = async (
    recommendation: LearningRecommendation,
    eventType: RecommendationEventType,
    extra: {
      progress?: number
      rating?: number
      reasonCode?: string
    } = {},
  ) => {
    setPendingAction(`${recommendation.id}:${eventType}`)
    try {
      await recordFeedback({
        projectId,
        recommendationId: recommendation.id,
        eventType,
        resourceId: recommendation.target_id ?? undefined,
        ...extra,
      })
      toast.success(
        eventType === 'completed'
          ? '已记录学习完成，后续验证任务将自动生成。'
          : '学习反馈已记录。',
      )
    } catch {
      toast.error('学习反馈记录失败，请稍后重试。')
    } finally {
      setPendingAction(null)
    }
  }

  if (Result.isInitial(overviewResult) || Result.isWaiting(overviewResult)) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        正在加载行动项执行反馈…
      </div>
    )
  }

  if (Result.isFailure(overviewResult)) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
        推荐执行反馈加载失败，请刷新后重试。
      </div>
    )
  }

  if (recommendations.length === 0) return null

  return (
    <div className="grid gap-3" data-testid="study-plan-action-feedback">
      {recommendations.map((recommendation) => {
        const interactions =
          overview?.interactionsByRecommendation[recommendation.id] ?? []
        const stage = getRecommendationStage(interactions)
        const targetMastery = toNumber(
          recommendation.expected_outcome.target_mastery,
        )
        const isTerminal = stage === 'completed' || stage === 'skipped'

        return (
          <article
            key={recommendation.id}
            className="space-y-3 rounded-md border bg-muted/30 p-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="size-4 shrink-0 text-primary" />
                  <div className="font-medium text-sm">
                    {studentFacingText(recommendation.title)}
                  </div>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {recommendation.reason_text
                    .map(studentFacingText)
                    .join('；') || '根据当前知识状态推荐。'}
                </p>
              </div>
              <Badge variant={stage === 'completed' ? 'default' : 'outline'}>
                {stageLabels[stage]}
              </Badge>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary" className="font-normal">
                {recommendationSourceLabel(recommendation)}
              </Badge>
              <span>目标掌握度：{percent(targetMastery)}</span>
              <span>推荐置信度：{percent(recommendation.score)}</span>
            </div>

            <Progress
              value={(stageOrder[stage] / 4) * 100}
              aria-label={`${recommendation.title}执行进度`}
            />

            {interactions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                {interactions.slice(-5).map((interaction) => (
                  <span
                    key={interaction.id}
                    className="rounded-full border bg-background px-2 py-1"
                  >
                    {eventLabels[interaction.event_type]}
                    {interaction.progress != null
                      ? ` ${percent(interaction.progress)}`
                      : ''}
                  </span>
                ))}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <RecommendationResourceLink
                projectId={projectId}
                recommendation={recommendation}
                onOpen={() => {
                  if (stage === 'unseen' || stage === 'seen') {
                    void submitFeedback(recommendation, 'clicked')
                  }
                }}
              />
              {!isTerminal && stage !== 'started' && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() =>
                    void submitFeedback(recommendation, 'started', {
                      progress: 0,
                    })
                  }
                  disabled={pendingAction !== null}
                >
                  <PlayCircle className="size-3.5" /> 开始学习
                </Button>
              )}
              {stage === 'started' && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() =>
                    void submitFeedback(recommendation, 'completed', {
                      progress: 1,
                    })
                  }
                  disabled={pendingAction !== null}
                >
                  <CheckCircle2 className="size-3.5" /> 完成学习
                </Button>
              )}
              {!isTerminal && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    void submitFeedback(recommendation, 'skipped', {
                      reasonCode: 'user_skipped_for_now',
                    })
                  }
                  disabled={pendingAction !== null}
                >
                  <SkipForward className="size-3.5" /> 暂时跳过
                </Button>
              )}
              {stage === 'completed' && (
                <>
                  <Select
                    value={ratings[recommendation.id] ?? '5'}
                    onValueChange={(value) =>
                      setRatings((current) => ({
                        ...current,
                        [recommendation.id]: value,
                      }))
                    }
                  >
                    <SelectTrigger
                      size="sm"
                      className="w-24"
                      aria-label={`${recommendation.title}评分`}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[5, 4, 3, 2, 1].map((rating) => (
                        <SelectItem key={rating} value={String(rating)}>
                          {rating} 星
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void submitFeedback(recommendation, 'rated', {
                        rating: Number(ratings[recommendation.id] ?? 5),
                      })
                    }
                    disabled={pendingAction !== null}
                  >
                    提交评分
                  </Button>
                </>
              )}
            </div>
          </article>
        )
      })}
    </div>
  )
}

export const StudyPlanClosedLoop = ({
  projectId,
  plan,
}: {
  projectId: string
  plan: AdaptedStudyPlan
}) => {
  const overviewResult = useAtomValue(closedLoopOverviewAtom(projectId))
  const diagnosisResult = useAtomValue(
    diagnosisOverviewAtom(
      plan.based_on_diagnosis_id
        ? JSON.stringify([projectId, plan.based_on_diagnosis_id])
        : '',
    ),
  )
  const recordFeedback = useAtomSet(recordRecommendationFeedbackAtom, {
    mode: 'promise',
  })
  const adjustPath = useAtomSet(adjustLearningPathAtom, { mode: 'promise' })
  const impressionRequests = useRef(new Set<string>())
  const [pendingAction, setPendingAction] = useState<string | null>(null)
  const [ratings, setRatings] = useState<Record<string, string>>({})

  const overview = Result.isSuccess(overviewResult)
    ? overviewResult.value
    : null
  const recommendationIds = new Set(plan.based_on_recommendation_ids)
  const recommendations = (overview?.recommendations ?? []).filter((item) =>
    recommendationIds.has(item.id),
  )

  useEffect(() => {
    if (!overview) return
    for (const recommendation of recommendations) {
      const interactions =
        overview.interactionsByRecommendation[recommendation.id] ?? []
      if (
        interactions.some((item) => item.event_type === 'impression') ||
        impressionRequests.current.has(recommendation.id)
      ) {
        continue
      }
      impressionRequests.current.add(recommendation.id)
      void recordFeedback({
        projectId,
        recommendationId: recommendation.id,
        eventType: 'impression',
        resourceId: recommendation.target_id ?? undefined,
      }).catch(() => impressionRequests.current.delete(recommendation.id))
    }
  }, [overview, projectId, recommendations, recordFeedback])

  const submitFeedback = async (
    recommendation: LearningRecommendation,
    eventType: RecommendationEventType,
    extra: {
      progress?: number
      rating?: number
      reasonCode?: string
    } = {},
  ) => {
    const key = `${recommendation.id}:${eventType}`
    setPendingAction(key)
    try {
      await recordFeedback({
        projectId,
        recommendationId: recommendation.id,
        eventType,
        resourceId: recommendation.target_id ?? undefined,
        ...extra,
      })
      toast.success(
        eventType === 'completed'
          ? '已记录真实学习完成，并生成验证任务。'
          : '学习反馈已记录。',
      )
    } catch {
      toast.error('学习反馈记录失败，请稍后重试。')
    } finally {
      setPendingAction(null)
    }
  }

  const verificationSteps = (plan.raw_learning_path.path_steps ?? []).filter(
    (step) => {
      if (step.type !== 'verification' || !step.recommendation_id) return false
      const interactions =
        overview?.interactionsByRecommendation[step.recommendation_id] ?? []
      return getRecommendationStage(interactions) === 'completed'
    },
  )
  const outcomes = (overview?.outcomes ?? []).filter((outcome) =>
    recommendationIds.has(outcome.recommendation_id),
  )
  const outcomeGroupsByRecommendation = new Map(
    groupInterventionOutcomes(outcomes).map((group) => [
      group.recommendationId,
      group,
    ]),
  )
  const outcomeGroups = recommendations.flatMap((recommendation) => {
    const group = outcomeGroupsByRecommendation.get(recommendation.id)
    return group ? [{ recommendation, ...group }] : []
  })
  const adjustedOutcomeIds = getAdjustedOutcomeIds(plan)
  const latestOutcomeIds = outcomeGroups.map((group) => group.latest.id)
  const allLatestOutcomesIncluded =
    latestOutcomeIds.length > 0 &&
    latestOutcomeIds.every((outcomeId) => adjustedOutcomeIds.has(outcomeId))
  const completedCount = recommendations.filter((recommendation) => {
    const interactions =
      overview?.interactionsByRecommendation[recommendation.id] ?? []
    return getRecommendationStage(interactions) === 'completed'
  }).length
  const startedCount = recommendations.filter((recommendation) => {
    const interactions =
      overview?.interactionsByRecommendation[recommendation.id] ?? []
    return stageOrder[getRecommendationStage(interactions)] >= 3
  }).length
  const diagnosis = Result.isSuccess(diagnosisResult)
    ? diagnosisResult.value?.diagnosis
    : null

  if (Result.isInitial(overviewResult) || Result.isWaiting(overviewResult)) {
    return (
      <section className="rounded-xl border bg-muted/20 p-5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          正在加载推荐执行与干预反馈…
        </div>
      </section>
    )
  }

  if (Result.isFailure(overviewResult)) {
    return (
      <section className="rounded-xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">
        学习闭环数据加载失败，请确认已完成 P0 数据库迁移并启动最新后端。
      </section>
    )
  }
  if (!overview) return null

  return (
    <section
      className="space-y-5 rounded-xl border bg-muted/20 p-5"
      aria-label="推荐执行与干预反馈"
      data-testid="study-plan-closed-loop"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-semibold">
            <RotateCw className="size-4 text-primary" />
            推荐—执行—验证—路径调整
          </h3>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            资源生成只代表“可使用”；只有你确认完成学习后，系统才会安排验证并评估掌握度增益。
          </p>
        </div>
        <Badge variant="outline">路径 v{plan.version}</Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          ['推荐', recommendations.length],
          ['已开始', startedCount],
          ['已完成', completedCount],
          ['已验证推荐', outcomeGroups.length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border bg-background p-3">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {value}
            </div>
          </div>
        ))}
      </div>

      {diagnosis && (
        <div className="space-y-3 rounded-lg border bg-background p-4">
          <div>
            <h4 className="text-sm font-semibold">诊断依据与可能根因</h4>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {diagnosis.summary || '系统已根据知识状态与练习证据生成诊断。'}
            </p>
          </div>
          {(diagnosis.root_causes ?? []).length > 0 ? (
            <ol className="space-y-2">
              {(diagnosis.root_causes ?? []).slice(0, 3).map((cause, index) => (
                <li
                  key={`${cause.type}-${cause.knowledge_point_id}-${index}`}
                  className="flex gap-3 rounded-md bg-muted/40 p-3 text-sm"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {index + 1}
                  </span>
                  <div>
                    <div className="font-medium">
                      {cause.type === 'weak_prerequisite'
                        ? '薄弱先修知识'
                        : cause.type === 'weak_mastery'
                          ? '当前知识点掌握不足'
                          : cause.type || '证据不足'}
                      {cause.confidence != null
                        ? ` · 可信度 ${percent(cause.confidence)}`
                        : ''}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {cause.reason_text || '可能与近期学习证据有关。'}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="text-xs text-muted-foreground">
              当前证据不足，系统不会输出高置信度根因；继续练习后再诊断。
            </div>
          )}
        </div>
      )}

      {plan.raw_learning_path.adjustment && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm">
          <div className="font-medium">为什么生成路径 v{plan.version}</div>
          {plan.raw_learning_path.adjustment.results?.length ? (
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              本版路径综合了{' '}
              {plan.raw_learning_path.adjustment.outcome_count ??
                plan.raw_learning_path.adjustment.results.length}{' '}
              项推荐的最新验证结果，覆盖{' '}
              {plan.raw_learning_path.adjustment.knowledge_point_count ?? '—'}{' '}
              个知识点；其中{' '}
              {plan.raw_learning_path.adjustment.target_achieved_count ?? 0}{' '}
              个达标，
              {plan.raw_learning_path.adjustment.needs_reinforcement_count ??
                0}{' '}
              个需要继续巩固。未达标知识点已按知识点去重添加补救步骤。
            </p>
          ) : (
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              验证后掌握度从{' '}
              {percent(plan.raw_learning_path.adjustment.mastery_before)} 变为{' '}
              {percent(plan.raw_learning_path.adjustment.mastery_after)}，目标为{' '}
              {percent(plan.raw_learning_path.adjustment.target_mastery)}。
              {plan.raw_learning_path.adjustment.target_achieved
                ? ' 已达到目标，路径继续进入后续内容。'
                : ' 尚未达到目标，路径增加了针对性练习与再次验证。'}
            </p>
          )}
        </div>
      )}

      {recommendations.length > 0 ? (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">推荐执行反馈</h4>
          {recommendations.map((recommendation) => {
            const interactions =
              overview.interactionsByRecommendation[recommendation.id] ?? []
            const stage = getRecommendationStage(interactions)
            const targetMastery = toNumber(
              recommendation.expected_outcome.target_mastery,
            )
            const withinHours = toNumber(
              recommendation.verification_plan.within_hours,
            )
            const isTerminal = stage === 'completed' || stage === 'skipped'
            return (
              <article
                key={recommendation.id}
                className="space-y-3 rounded-lg border bg-background p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium">
                      {studentFacingText(recommendation.title)}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {recommendation.reason_text
                        .map(studentFacingText)
                        .join('；') || '根据当前知识状态推荐。'}
                    </div>
                    <Badge variant="secondary" className="mt-2 font-normal">
                      {recommendationSourceLabel(recommendation)}
                    </Badge>
                  </div>
                  <Badge
                    variant={stage === 'completed' ? 'default' : 'outline'}
                  >
                    {stageLabels[stage]}
                  </Badge>
                </div>

                <div className="grid gap-2 text-xs sm:grid-cols-3">
                  <div className="rounded-md bg-muted/50 p-2.5">
                    目标掌握度：{percent(targetMastery)}
                  </div>
                  <div className="rounded-md bg-muted/50 p-2.5">
                    验证窗口：{withinHours ? `${withinHours} 小时` : '待确定'}
                  </div>
                  <div className="rounded-md bg-muted/50 p-2.5">
                    推荐置信度：{percent(recommendation.score)}
                  </div>
                </div>

                <Progress
                  value={(stageOrder[stage] / 4) * 100}
                  aria-label={`${recommendation.title}执行进度`}
                />

                {interactions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                    {interactions.slice(-5).map((interaction) => (
                      <span
                        key={interaction.id}
                        className="rounded-full border px-2 py-1"
                      >
                        {eventLabels[interaction.event_type]}
                        {interaction.progress != null
                          ? ` ${percent(interaction.progress)}`
                          : ''}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-2">
                  <RecommendationResourceLink
                    projectId={projectId}
                    recommendation={recommendation}
                    onOpen={() => {
                      if (stage === 'unseen' || stage === 'seen') {
                        void submitFeedback(recommendation, 'clicked')
                      }
                    }}
                  />
                  {!isTerminal && stage !== 'started' && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() =>
                        void submitFeedback(recommendation, 'started', {
                          progress: 0,
                        })
                      }
                      disabled={pendingAction !== null}
                    >
                      <PlayCircle className="size-3.5" /> 开始学习
                    </Button>
                  )}
                  {stage === 'started' && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() =>
                        void submitFeedback(recommendation, 'completed', {
                          progress: 1,
                        })
                      }
                      disabled={pendingAction !== null}
                    >
                      <CheckCircle2 className="size-3.5" /> 完成学习
                    </Button>
                  )}
                  {!isTerminal && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        void submitFeedback(recommendation, 'skipped', {
                          reasonCode: 'user_skipped_for_now',
                        })
                      }
                      disabled={pendingAction !== null}
                    >
                      <SkipForward className="size-3.5" /> 暂时跳过
                    </Button>
                  )}
                  {stage === 'completed' && (
                    <>
                      <Select
                        value={ratings[recommendation.id] ?? '5'}
                        onValueChange={(value) =>
                          setRatings((current) => ({
                            ...current,
                            [recommendation.id]: value,
                          }))
                        }
                      >
                        <SelectTrigger
                          size="sm"
                          className="w-24"
                          aria-label={`${recommendation.title}评分`}
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[5, 4, 3, 2, 1].map((rating) => (
                            <SelectItem key={rating} value={String(rating)}>
                              {rating} 星
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          void submitFeedback(recommendation, 'rated', {
                            rating: Number(ratings[recommendation.id] ?? 5),
                          })
                        }
                        disabled={pendingAction !== null}
                      >
                        提交评分
                      </Button>
                    </>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed bg-background p-4 text-sm text-muted-foreground">
          当前路径没有关联推荐。重新生成学习计划后，系统会把推荐执行状态展示在这里。
        </div>
      )}

      <div className="space-y-3 border-t pt-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold">
          <ClipboardCheck className="size-4 text-primary" />
          验证任务
        </h4>
        {verificationSteps.length > 0 ? (
          verificationSteps.map((step, index) => {
            const relatedRecommendation = recommendations.find(
              (item) => item.id === step.recommendation_id,
            )
            const canVerify = Boolean(
              step.id &&
              step.target_id &&
              step.recommendation_id &&
              step.knowledge_point_id,
            )
            const generationStatus = String(
              step.acceptance_condition &&
                typeof step.acceptance_condition === 'object'
                ? (step.acceptance_condition.generation_status ?? 'generating')
                : 'generating',
            )
            return (
              <div
                key={step.id ?? `verification-${index}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-background p-4"
              >
                <div>
                  <div className="font-medium">
                    {step.title || '完成推荐后的验证练习'}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    基线 {percent(step.baseline_mastery)} · 目标{' '}
                    {percent(step.target_mastery)} · 状态{' '}
                    {step.status === 'completed'
                      ? '已完成'
                      : generationStatus === 'failed'
                        ? '验证题生成失败'
                        : step.target_id
                          ? '独立验证题已创建'
                          : '旧记录待补生成'}
                  </div>
                </div>
                {step.status === 'completed' ? (
                  <Badge>验证已完成</Badge>
                ) : canVerify ? (
                  <Button size="sm" asChild>
                    <Link
                      to="/dashboard/p/$projectId/q/$quizId"
                      params={{ projectId, quizId: step.target_id! }}
                      onClick={() =>
                        activateLearningVerification({
                          projectId,
                          recommendationId: step.recommendation_id!,
                          learningPathId: plan.learning_path_id,
                          learningPathStepId: step.id!,
                          knowledgePointId: step.knowledge_point_id!,
                          objective:
                            step.title || '完成推荐后的同知识点验证练习',
                        })
                      }
                    >
                      打开专属验证题 <ArrowUpRight className="size-3.5" />
                    </Link>
                  </Button>
                ) : relatedRecommendation ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={pendingAction !== null}
                    onClick={() =>
                      void submitFeedback(relatedRecommendation, 'completed', {
                        progress: 1,
                      })
                    }
                  >
                    补生成专属验证题
                  </Button>
                ) : (
                  <Badge variant="outline">旧验证记录不可用</Badge>
                )}
              </div>
            )
          })
        ) : (
          <div className="flex items-center gap-2 rounded-lg border border-dashed bg-background p-4 text-sm text-muted-foreground">
            <CircleDashed className="size-4" />
            完成一项推荐后，系统会在这里生成同知识点验证任务。
          </div>
        )}
      </div>

      <div className="space-y-3 border-t pt-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold">
          <Target className="size-4 text-primary" />
          干预效果与路径调整
        </h4>
        {outcomeGroups.length > 0 ? (
          <>
            {outcomeGroups.map(({ recommendation, latest, history }) => {
              const outcome = latest
              const includedInAdjustment = adjustedOutcomeIds.has(outcome.id)
              return (
                <div
                  key={recommendation.id}
                  className="rounded-lg border bg-background p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="mb-1 text-xs font-medium text-primary">
                        {recommendation.title}
                      </div>
                      <div className="font-medium">
                        掌握度 {percent(outcome.mastery_before)} →{' '}
                        {percent(outcome.mastery_after)}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        增益 {percent(outcome.mastery_gain)} · 验证得分{' '}
                        {percent(outcome.verification_score)} · 归因可信度{' '}
                        {percent(outcome.attribution_confidence)}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {includedInAdjustment ? (
                        <Badge variant="outline">已纳入当前路径</Badge>
                      ) : null}
                      <Badge
                        variant={
                          outcome.target_achieved ? 'default' : 'secondary'
                        }
                      >
                        {outcome.target_achieved ? '达到目标' : '需要继续巩固'}
                      </Badge>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      评估窗口：{outcome.evaluation_window_hours} 小时
                    </span>
                  </div>
                  {history.length > 0 ? (
                    <Collapsible className="group/history mt-3 border-t pt-3">
                      <CollapsibleTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-auto w-full justify-between px-0 text-xs text-muted-foreground hover:bg-transparent hover:text-foreground"
                        >
                          <span className="flex items-center gap-1.5">
                            <History className="size-3.5" />
                            历史验证记录（{history.length}）
                          </span>
                          <ChevronDown className="size-3.5 transition-transform group-data-[state=open]/history:rotate-180" />
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent className="mt-2 space-y-2">
                        {history.map((historicalOutcome, index) => (
                          <div
                            key={historicalOutcome.id}
                            className="rounded-md border bg-muted/30 p-3 text-xs"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium">
                                第 {history.length - index} 次验证 · 掌握度{' '}
                                {percent(historicalOutcome.mastery_before)} →{' '}
                                {percent(historicalOutcome.mastery_after)}
                              </span>
                              <Badge
                                variant={
                                  historicalOutcome.target_achieved
                                    ? 'default'
                                    : 'secondary'
                                }
                              >
                                {historicalOutcome.target_achieved
                                  ? '达到目标'
                                  : '需要继续巩固'}
                              </Badge>
                            </div>
                            <div className="mt-1 text-muted-foreground">
                              验证得分{' '}
                              {percent(historicalOutcome.verification_score)} ·
                              增益 {percent(historicalOutcome.mastery_gain)} ·
                              评估时间{' '}
                              {new Date(
                                historicalOutcome.evaluated_at,
                              ).toLocaleString('zh-CN')}
                            </div>
                          </div>
                        ))}
                      </CollapsibleContent>
                    </Collapsible>
                  ) : null}
                </div>
              )
            })}
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">
                    综合调整当前学习路径
                  </div>
                  <div className="mt-1 text-xs leading-5 text-muted-foreground">
                    系统将综合 {latestOutcomeIds.length}{' '}
                    项推荐的最新验证结果，并按知识点去重生成补救步骤。
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  disabled={
                    plan.status !== 'active' ||
                    allLatestOutcomesIncluded ||
                    pendingAction !== null
                  }
                  onClick={async () => {
                    setPendingAction('adjust:all')
                    try {
                      await adjustPath({
                        projectId,
                        pathId: plan.learning_path_id,
                        outcomeIds: latestOutcomeIds,
                      })
                      toast.success(
                        `已综合 ${latestOutcomeIds.length} 项最新验证结果生成新版学习路径。`,
                      )
                    } catch {
                      toast.error(
                        '综合路径调整失败，验证结果可能已更新，请刷新后重试。',
                      )
                    } finally {
                      setPendingAction(null)
                    }
                  }}
                >
                  {allLatestOutcomesIncluded
                    ? '最新结果已全部纳入当前路径'
                    : `综合调整学习路径（${latestOutcomeIds.length} 项）`}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-lg border border-dashed bg-background p-4 text-sm text-muted-foreground">
            完成验证练习后，这里会展示干预前后掌握度、增益、目标达成情况和归因可信度。
          </div>
        )}
      </div>
    </section>
  )
}
