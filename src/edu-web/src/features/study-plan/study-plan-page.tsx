import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  generateStudyPlanAtom,
  latestStudyPlanRemoteAtom,
  studyPlanProgressAtom,
  studyPlansHistoryRemoteAtom,
} from '@/data-acess/study-plan'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  BrainCircuit,
  CalendarDays,
  History,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'
import { StudyPlanHeader } from './components/study-plan-header'

interface StudyPlanPageProps {
  projectId: string
}

export const StudyPlanPage = ({ projectId }: StudyPlanPageProps) => {
  const latestPlanResult = useAtomValue(latestStudyPlanRemoteAtom(projectId))
  const historyResult = useAtomValue(studyPlansHistoryRemoteAtom(projectId))
  const generationProgress = useAtomValue(studyPlanProgressAtom)

  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

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

  const handleGenerate = async () => {
    setIsGenerating(true)
    try {
      await generatePlan(projectId)
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
        <div className="container mx-auto max-w-5xl py-8 space-y-8">
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
            <div className="flex items-center gap-2">
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
            <div
              className="flex items-center gap-3 rounded-lg border bg-muted/40 px-4 py-3 text-sm"
              role="status"
              aria-live="polite"
            >
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
              <span>{generationProgress.message}</span>
            </div>
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
                          <p className="mt-1 text-sm text-muted-foreground">
                            {step.reason}
                          </p>
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
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-6 space-y-6">
                      {/* Analysis */}
                      <div>
                        <h3 className="text-lg font-semibold mb-2">分析</h3>
                        <p className="text-muted-foreground">
                          {displayedPlan.content.analysis}
                        </p>
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
                                    <div className="text-xs text-muted-foreground">
                                      {item.description}
                                    </div>
                                  )}
                                </div>
                                <span className="text-xs uppercase tracking-wider font-bold text-muted-foreground opacity-70 border px-1.5 py-0.5 rounded">
                                  {item.source_type || item.type}
                                </span>
                              </div>
                            )

                            if (!item.is_navigable) {
                              return (
                                <div key={i} className="block">
                                  {content}
                                </div>
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
                                        quizId: item.parent_id || item.id,
                                      }
                                    : {
                                        projectId,
                                        flashcardGroupId:
                                          item.parent_id || item.id,
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
                                  <li key={j}>{task}</li>
                                ))}
                              </ul>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Encouragement */}
                      <div className="bg-primary/5 p-4 rounded-lg border border-primary/10">
                        <p className="font-medium text-primary italic text-center">
                          "{displayedPlan.content.encouragement}"
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">薄弱主题</CardTitle>
                      <CardDescription>需要提升的领域</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {displayedPlan.weak_topics &&
                      displayedPlan.weak_topics.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {displayedPlan.weak_topics.map((topic, i) => (
                            <span
                              key={i}
                              className="px-3 py-1 rounded-full bg-destructive/10 text-destructive text-sm font-medium"
                            >
                              {topic}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          暂未识别出具体薄弱主题。继续练习吧！
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  <Card className="bg-muted/50">
                    <CardHeader>
                      <CardTitle className="text-lg">工作原理</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground space-y-2">
                      <p>1. 分析你的测验结果和闪卡表现。</p>
                      <p>2. 找出正确率低于 70% 的主题。</p>
                      <p>3. AI 智能体生成定制日程，并推荐具体学习资源。</p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center min-h-[400px] text-center p-8 border-2 border-dashed rounded-lg bg-muted/30">
                <div className="bg-background p-4 rounded-full shadow-sm mb-4">
                  <BrainCircuit className="h-12 w-12 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">还没有学习计划</h3>
                <p className="text-muted-foreground max-w-md mb-6">
                  生成第一个个性化学习计划，根据你的表现获得定制学习路线。
                </p>
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
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
