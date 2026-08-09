import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ArrowUpRight,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  Circle,
  History,
  Loader2,
  PenLine,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'
import { StudyPlanCalendar } from './components/study-plan-calendar'
import { StudyPlanClosedLoop } from './components/study-plan-closed-loop'
import { StudyPlanHeader } from './components/study-plan-header'
import { loadCustomStudyPlan } from './custom-study-plan'
import {
  generateStudyPlanAtom,
  latestStudyPlanRemoteAtom,
  studyPlanProgressAtom,
  studyPlansHistoryRemoteAtom,
} from '@/data-acess/study-plan'
import { refreshClosedLoopOverviewAtom } from '@/data-acess/learning-closed-loop'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Response } from '@/components/ai-elements/response'

interface StudyPlanPageProps {
  projectId: string
}

const generationStages = [
  {
    agent: 'ProfileAgent',
    title: '分析学习画像',
    description: '整理学习记录与个人偏好',
  },
  {
    agent: 'KTAgent',
    title: '评估知识掌握',
    description: '计算知识点掌握度与证据置信度',
  },
  {
    agent: 'DiagnosisAgent',
    title: '诊断薄弱点',
    description: '识别主要弱项与可能根因',
  },
  {
    agent: 'ResourceAgent',
    title: '生成学习推荐',
    description: '匹配学习资源或生成针对性练习建议',
  },
  {
    agent: 'PlannerAgent',
    title: '编排学习路径',
    description: '将推荐安排成可执行学习步骤',
  },
] as const

const resourceTypeLabels: Record<string, string> = {
  quiz: '选择题',
  practice: '专项练习',
  flashcard: '闪卡',
  flashcards: '闪卡',
  note: '笔记',
  mind_map: '知识导图',
  verification: '验证测验',
  resource: '学习资源',
}

export const StudyPlanPage = ({ projectId }: StudyPlanPageProps) => {
  const latestPlanResult = useAtomValue(latestStudyPlanRemoteAtom(projectId))
  const historyResult = useAtomValue(studyPlansHistoryRemoteAtom(projectId))
  const generationProgress = useAtomValue(studyPlanProgressAtom)

  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [customEntries] = useState(() => loadCustomStudyPlan(projectId))

  // Determine which plan to show: selected or latest
  const historyPlans = Result.isSuccess(historyResult)
    ? historyResult.value
    : []
  const latestPlan = Result.isSuccess(latestPlanResult)
    ? latestPlanResult.value
    : null

  const displayedPlan = selectedPlanId
    ? historyPlans.find((p) => p.id === selectedPlanId)
    : latestPlan
  const streamingPath = isGenerating
    ? generationProgress?.partialPlan
    : undefined
  const activeGenerationStage = generationStages.findIndex(
    (stage) => stage.agent === generationProgress?.agentName,
  )

  const plannerModeLabel =
    displayedPlan?.planner_mode === 'llm'
      ? 'LLM'
      : displayedPlan?.planner_mode === 'rule_fallback'
        ? 'Fallback'
        : displayedPlan?.planner_mode === 'rule'
          ? 'Rule'
          : 'Unknown'

  // Update selected plan if we just loaded history and possess a latest plan but weren't selecting anything
  // Actually, default behavior is to show latestPlan if selectedPlanId is null.

  const generatePlan = useAtomSet(generateStudyPlanAtom, {
    mode: 'promise',
  })
  const refreshClosedLoop = useAtomSet(refreshClosedLoopOverviewAtom, {
    mode: 'promise',
  })
  const handleGenerate = async () => {
    setIsGenerating(true)
    try {
      await generatePlan(projectId)
      await refreshClosedLoop(projectId)
    } catch {
      // The generation atom displays the failure toast.
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="flex h-full flex-col max-h-screen">
      <StudyPlanHeader projectId={projectId} />
      <div className="flex flex-1 flex-col min-h-0 overflow-y-auto">
        <div className="container mx-auto max-w-7xl space-y-8 px-4 py-8">
          <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                <BrainCircuit className="h-8 w-8 text-primary" />
                个性化学习计划
              </h1>
              <p className="text-muted-foreground mt-1">
                基于 AI 分析你的学习表现，优化学习路径。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="lg" asChild>
                <Link
                  to="/dashboard/p/$projectId/study-plan/customize"
                  params={{ projectId }}
                >
                  <PenLine className="mr-2 size-4" />
                  我要自定义学习计划
                </Link>
              </Button>
              {displayedPlan && (
                <div className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
                  <span className="text-muted-foreground">规划模式</span>
                  <span className="font-semibold">{plannerModeLabel}</span>
                </div>
              )}
              {historyPlans.length > 0 && (
                <Select
                  value={selectedPlanId || 'latest'}
                  onValueChange={(val) =>
                    setSelectedPlanId(val === 'latest' ? null : val)
                  }
                >
                  <SelectTrigger className="w-[180px]">
                    <History className="mr-2 h-4 w-4" />
                    <SelectValue placeholder="历史记录" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="latest">最新计划</SelectItem>
                    {historyPlans.map((plan) => (
                      <SelectItem key={plan.id} value={plan.id}>
                        {new Date(plan.created_at).toLocaleDateString()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              <Button
                onClick={handleGenerate}
                disabled={isGenerating}
                size="lg"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    正在分析...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    生成新计划
                  </>
                )}
              </Button>
            </div>
          </div>

          {isGenerating && generationProgress && (
            <Card
              className="border-primary/20 bg-muted/20"
              role="status"
              aria-live="polite"
            >
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  {generationProgress.message}
                </CardTitle>
                <CardDescription>
                  系统将先生成可执行推荐，再把推荐编排进学习路径。
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <ol className="grid gap-3 md:grid-cols-5">
                  {generationStages.map((stage, index) => {
                    const completed = activeGenerationStage > index
                    const active = activeGenerationStage === index
                    return (
                      <li
                        key={stage.agent}
                        className={`rounded-lg border p-3 ${
                          active
                            ? 'border-primary/40 bg-primary/5'
                            : completed
                              ? 'border-emerald-500/30 bg-emerald-500/5'
                              : 'bg-background/60'
                        }`}
                      >
                        <div className="flex items-center gap-2 text-sm font-medium">
                          {completed ? (
                            <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                          ) : active ? (
                            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
                          ) : (
                            <Circle className="size-4 shrink-0 text-muted-foreground/50" />
                          )}
                          {stage.title}
                        </div>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                          {stage.description}
                        </p>
                      </li>
                    )
                  })}
                </ol>

                {(generationProgress.recommendations?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-primary/20 bg-background p-4">
                    <div className="mb-2 text-sm font-semibold">
                      已生成 {generationProgress.recommendations?.length}{' '}
                      条学习推荐
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                      {generationProgress.recommendations?.map(
                        (recommendation) => (
                          <div
                            key={recommendation.id}
                            className="rounded-md bg-muted/40 px-3 py-2"
                          >
                            <div className="text-sm font-medium">
                              {recommendation.title}
                            </div>
                            {recommendation.reason_text.length > 0 && (
                              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                {recommendation.reason_text.join('；')}
                              </p>
                            )}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {streamingPath && (
            <Card className="border-primary/30 shadow-sm">
              <CardHeader className="border-b">
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Sparkles className="h-5 w-5 animate-pulse text-primary" />
                  {streamingPath.title || '正在生成个性化学习路径…'}
                </CardTitle>
                {streamingPath.estimated_minutes ? (
                  <CardDescription>
                    预计学习时长：{streamingPath.estimated_minutes} 分钟
                  </CardDescription>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-4 pt-6">
                {(streamingPath.path_steps ?? []).length > 0 && (
                  <div className="space-y-3">
                    {(streamingPath.path_steps ?? []).map((step, index) => (
                      <div
                        key={step.step_no ?? step.target_id ?? index}
                        className="rounded-md border bg-muted/30 p-3"
                      >
                        <div className="font-medium">
                          {step.step_no ?? index + 1}.{' '}
                          {step.title || '正在生成步骤内容…'}
                        </div>
                        {step.reason && (
                          <Response className="mt-1 text-sm text-muted-foreground">
                            {step.reason}
                          </Response>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {(streamingPath.based_on_knowledge_points ?? []).length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {(streamingPath.based_on_knowledge_points ?? []).map(
                      (point) => (
                        <span
                          key={point}
                          className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary"
                        >
                          {point}
                        </span>
                      ),
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="grid gap-6">
            {displayedPlan ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                  <Card className="border shadow-lg">
                    <CardHeader className="border-b">
                      <CardTitle className="text-xl flex items-center gap-2">
                        <CalendarDays className="h-5 w-5 text-primary" />
                        你的结构化计划
                      </CardTitle>
                      <CardDescription>
                        生成时间：{' '}
                        {new Date(displayedPlan.created_at).toLocaleString()}
                        {' · '}路径 v{displayedPlan.version}
                        {displayedPlan.previous_path_id ? '（已调整）' : ''}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-6 space-y-6">
                      <StudyPlanClosedLoop
                        projectId={projectId}
                        plan={displayedPlan}
                      />

                      {/* Analysis */}
                      <div>
                        <h3 className="text-lg font-semibold mb-2">分析</h3>
                        <Response className="text-muted-foreground">
                          {displayedPlan.content.analysis}
                        </Response>
                      </div>

                      {/* Focus Areas */}
                      {displayedPlan.content.focus_areas.length > 0 && (
                        <div>
                          <h3 className="text-lg font-semibold mb-2">
                            重点关注
                          </h3>
                          <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                            {displayedPlan.content.focus_areas.map(
                              (area, i) => (
                                <li key={i}>{area}</li>
                              ),
                            )}
                          </ol>
                        </div>
                      )}

                      {/* Action Items */}
                      <div>
                        <h3 className="text-lg font-semibold mb-2">行动项</h3>
                        <div className="grid gap-2">
                          {displayedPlan.content.action_items.map((item, i) => {
                            const isQuiz = item.type === 'quiz'
                            const targetId = item.parent_id || item.id
                            const hasDirectTarget =
                              item.is_navigable &&
                              Boolean(targetId) &&
                              !targetId.startsWith('path-step-')
                            const content = (
                              <div className="flex items-center gap-2 p-3 rounded-md bg-muted/50 hover:bg-muted transition-colors border">
                                {isQuiz ? (
                                  <BrainCircuit className="h-4 w-4 text-blue-500" />
                                ) : (
                                  <Sparkles className="h-4 w-4 text-[#5483B3]" />
                                )}
                                <div className="flex-1">
                                  <div className="font-medium text-sm">
                                    {item.title}
                                  </div>
                                  {item.description && (
                                    <Response className="text-xs text-muted-foreground">
                                      {item.description}
                                    </Response>
                                  )}
                                </div>
                                <span className="rounded border px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                                  {resourceTypeLabels[
                                    item.source_type || item.type
                                  ] ?? '学习资源'}
                                </span>
                                <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />
                              </div>
                            )

                            if (!hasDirectTarget) {
                              return (
                                <Link
                                  key={i}
                                  to={
                                    isQuiz
                                      ? '/dashboard/p/$projectId/learning-evaluation/practice'
                                      : '/dashboard/p/$projectId/resource-packages'
                                  }
                                  params={{ projectId }}
                                  className="block"
                                >
                                  {content}
                                </Link>
                              )
                            }

                            return (
                              <Link
                                key={i}
                                to={
                                  isQuiz
                                    ? '/dashboard/p/$projectId/q/$quizId'
                                    : '/dashboard/p/$projectId/f/$flashcardGroupId'
                                }
                                params={
                                  isQuiz
                                    ? {
                                        projectId,
                                        quizId: targetId,
                                      }
                                    : {
                                        projectId,
                                        flashcardGroupId: targetId,
                                      }
                                }
                                className="block"
                              >
                                {content}
                              </Link>
                            )
                          })}
                        </div>
                      </div>

                      {/* Schedule */}
                      <div>
                        <h3 className="text-lg font-semibold mb-2">每周安排</h3>
                        <div className="space-y-4">
                          {displayedPlan.content.schedule.map((day, i) => (
                            <div
                              key={i}
                              className="border-l-2 border-primary/20 pl-4 py-1"
                            >
                              <div className="font-medium text-sm">
                                {day.day}
                              </div>
                              <ul className="list-disc list-inside text-sm text-muted-foreground mt-1">
                                {day.tasks.map((task, j) => (
                                  <li key={j}>
                                    <Response className="inline text-sm">
                                      {task}
                                    </Response>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Encouragement */}
                      <div className="bg-primary/5 p-4 rounded-lg border border-primary/10">
                        <Response className="font-medium text-primary italic text-center">
                          {`"${displayedPlan.content.encouragement}"`}
                        </Response>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <div className="space-y-6">
                  <StudyPlanCalendar
                    generatedAt={displayedPlan.created_at}
                    schedule={displayedPlan.content.schedule}
                    customEntries={customEntries}
                  />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="flex min-h-[400px] flex-col items-center justify-center border-2 border-dashed bg-muted/30 p-8 text-center lg:col-span-2">
                  <div className="mb-4 rounded-full bg-background p-4 shadow-sm">
                    <BrainCircuit className="h-12 w-12 text-primary" />
                  </div>
                  <h3 className="mb-2 text-xl font-semibold">还没有学习计划</h3>
                  <p className="mb-6 max-w-md text-muted-foreground">
                    生成第一个个性化学习计划，或先手动安排未来 7 天的学习任务。
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button onClick={handleGenerate} disabled={isGenerating}>
                      {isGenerating ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          正在生成...
                        </>
                      ) : (
                        '生成我的第一个计划'
                      )}
                    </Button>
                    <Button variant="outline" asChild>
                      <Link
                        to="/dashboard/p/$projectId/study-plan/customize"
                        params={{ projectId }}
                      >
                        自定义 7 天计划
                      </Link>
                    </Button>
                  </div>
                </div>
                <StudyPlanCalendar
                  generatedAt={new Date().toISOString()}
                  schedule={[]}
                  customEntries={customEntries}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
