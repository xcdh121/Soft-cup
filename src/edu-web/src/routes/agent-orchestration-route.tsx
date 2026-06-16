import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Activity,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  Play,
  RefreshCw,
  Route,
  Sparkles,
} from 'lucide-react'
import { useMemo, useState } from 'react'

const DEFAULT_PROJECT_ID = '3fc72376-bec9-4675-98ac-5f46c5419e50'
const API_BASE = import.meta.env.VITE_SERVER_URL ?? 'http://localhost:8000'

type AgentEvent = {
  event_type: string
  run_id: string
  agent_name?: string | null
  status: string
  summary: string
  timestamp: string
  payload: Record<string, unknown>
}

type DiagnosisResponse = {
  diagnosis_id: string
  run_id: string
  project_id: string
  student_id: string
  status: string
  diagnosis: Record<string, unknown>
  recommendations: Array<Record<string, unknown>>
  learning_path?: Record<string, unknown> | null
  next_actions: string[]
  created_at: string
}

type RecommendationsResponse = {
  run_id: string
  project_id: string
  recommendations: Array<Record<string, unknown>>
  based_on_diagnosis_id?: string | null
  created_at: string
}

type LearningPathResponse = {
  path_id: string
  run_id: string
  project_id: string
  learning_path: Record<string, unknown>
  based_on_diagnosis_id?: string | null
  based_on_recommendation_ids: string[]
  created_at: string
}

const requestJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `${response.status} ${response.statusText}`)
  }

  return response.json() as Promise<T>
}

const JsonBlock = ({ value }: { value: unknown }) => {
  return (
    <pre className="max-h-80 overflow-auto rounded-md border bg-muted/50 p-3 font-mono text-xs leading-5 text-foreground">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  )
}

const StatusPill = ({ status }: { status: string }) => {
  const isCompleted = status === 'completed'
  const isFailed = status === 'failed'

  return (
    <span
      className={[
        'inline-flex h-6 items-center rounded-full border px-2 text-xs font-medium',
        isCompleted
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : isFailed
            ? 'border-red-200 bg-red-50 text-red-700'
            : 'border-amber-200 bg-amber-50 text-amber-700',
      ].join(' ')}
    >
      {status}
    </span>
  )
}

const EmptyState = ({ text }: { text: string }) => {
  return (
    <div className="flex min-h-28 items-center justify-center rounded-md border border-dashed bg-muted/30 px-4 text-center text-sm text-muted-foreground">
      {text}
    </div>
  )
}

export const AgentOrchestrationRoute = () => {
  const [projectId, setProjectId] = useState(DEFAULT_PROJECT_ID)
  const [diagnosis, setDiagnosis] = useState<DiagnosisResponse | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [recommendations, setRecommendations] =
    useState<RecommendationsResponse | null>(null)
  const [learningPath, setLearningPath] = useState<LearningPathResponse | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState(false)
  const [activeAction, setActiveAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const completedAgents = useMemo(() => {
    return events.filter((event) => event.event_type === 'agent_step').length
  }, [events])

  const runStartedAt = events[0]?.timestamp
    ? new Date(events[0].timestamp).toLocaleString()
    : '未开始'

  const runDiagnosis = async () => {
    setIsLoading(true)
    setActiveAction('diagnosis')
    setError(null)
    setEvents([])
    setRecommendations(null)
    setLearningPath(null)

    try {
      const nextDiagnosis = await requestJson<DiagnosisResponse>(
        `/api/v1/projects/${projectId}/diagnosis`,
        {
          method: 'POST',
          body: JSON.stringify({
            trigger: {
              type: 'manual',
              id: 'ui_debug',
            },
          }),
        },
      )

      setDiagnosis(nextDiagnosis)
      const nextEvents = await requestJson<AgentEvent[]>(
        `/api/v1/projects/${projectId}/diagnosis/${nextDiagnosis.diagnosis_id}/trace`,
      )
      setEvents(nextEvents)
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败')
    } finally {
      setIsLoading(false)
      setActiveAction(null)
    }
  }

  const refreshTrace = async () => {
    if (!diagnosis) return
    setActiveAction('trace')
    setError(null)

    try {
      const nextEvents = await requestJson<AgentEvent[]>(
        `/api/v1/projects/${projectId}/diagnosis/${diagnosis.diagnosis_id}/trace`,
      )
      setEvents(nextEvents)
    } catch (err) {
      setError(err instanceof Error ? err.message : '读取 trace 失败')
    } finally {
      setActiveAction(null)
    }
  }

  const runRecommendations = async () => {
    if (!diagnosis) return
    setActiveAction('recommendations')
    setError(null)

    try {
      const nextRecommendations = await requestJson<RecommendationsResponse>(
        `/api/v1/projects/${projectId}/recommendations/generate`,
        {
          method: 'POST',
          body: JSON.stringify({
            diagnosis_id: diagnosis.diagnosis_id,
          }),
        },
      )
      setRecommendations(nextRecommendations)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成推荐失败')
    } finally {
      setActiveAction(null)
    }
  }

  const runLearningPath = async () => {
    if (!diagnosis) return
    setActiveAction('learning-path')
    setError(null)

    try {
      const nextLearningPath = await requestJson<LearningPathResponse>(
        `/api/v1/projects/${projectId}/learning-paths/generate`,
        {
          method: 'POST',
          body: JSON.stringify({
            diagnosis_id: diagnosis.diagnosis_id,
          }),
        },
      )
      setLearningPath(nextLearningPath)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成学习路径失败')
    } finally {
      setActiveAction(null)
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Activity className="size-4" />
              多智能体协同编排调试台
            </div>
            <h1 className="text-2xl font-semibold tracking-normal">
              Agent Orchestration Trace
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              在浏览器中直接触发诊断、推荐和学习路径生成，查看每个 Agent
              的执行阶段、结构化结果和数据库回读状态。
            </p>
          </div>

          <div className="grid w-full gap-2 sm:grid-cols-[minmax(0,1fr)_auto] lg:w-[560px]">
            <Input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="Project ID"
            />
            <Button onClick={runDiagnosis} disabled={isLoading || !projectId}>
              {activeAction === 'diagnosis' ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              生成诊断
            </Button>
          </div>
        </div>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-4">
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <BrainCircuit className="size-5 text-primary" />
              <div>
                <div className="text-sm text-muted-foreground">Run ID</div>
                <div className="max-w-52 truncate text-sm font-medium">
                  {diagnosis?.run_id ?? '未生成'}
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <CheckCircle2 className="size-5 text-primary" />
              <div>
                <div className="text-sm text-muted-foreground">已完成步骤</div>
                <div className="text-sm font-medium">{completedAgents} / 6</div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <Sparkles className="size-5 text-primary" />
              <div>
                <div className="text-sm text-muted-foreground">诊断状态</div>
                <div className="text-sm font-medium">
                  {diagnosis?.status ?? '未开始'}
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <Route className="size-5 text-primary" />
              <div>
                <div className="text-sm text-muted-foreground">开始时间</div>
                <div className="text-sm font-medium">{runStartedAt}</div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Card className="rounded-lg">
            <CardHeader className="gap-2">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle>协同过程 Trace</CardTitle>
                  <CardDescription>
                    从数据库读取 AgentEvent，按执行时间排序展示。
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  onClick={refreshTrace}
                  disabled={!diagnosis || activeAction === 'trace'}
                >
                  {activeAction === 'trace' ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw className="size-4" />
                  )}
                  刷新
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <EmptyState text="点击生成诊断后，这里会展示 run_started、agent_step、artifact_updated 和 run_completed。" />
              ) : (
                <div className="space-y-3">
                  {events.map((event, index) => (
                    <div
                      key={`${event.event_type}-${event.timestamp}-${index}`}
                      className="grid gap-3 rounded-md border bg-card p-3 sm:grid-cols-[160px_minmax(0,1fr)_auto]"
                    >
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </div>
                        <div className="text-sm font-medium">
                          {event.agent_name ?? event.event_type}
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {event.summary}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {event.event_type}
                        </div>
                      </div>
                      <StatusPill status={event.status} />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6">
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle>诊断结果</CardTitle>
                <CardDescription>
                  DiagnosisAgent 产出的结构化根因诊断。
                </CardDescription>
              </CardHeader>
              <CardContent>
                {diagnosis ? (
                  <JsonBlock value={diagnosis.diagnosis} />
                ) : (
                  <EmptyState text="暂无诊断结果" />
                )}
              </CardContent>
            </Card>

            <Card className="rounded-lg">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>资源推荐</CardTitle>
                    <CardDescription>
                      ResourceAgent 产出的推荐项。
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    onClick={runRecommendations}
                    disabled={!diagnosis || activeAction === 'recommendations'}
                  >
                    {activeAction === 'recommendations' ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}
                    生成
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {recommendations ? (
                  <JsonBlock value={recommendations.recommendations} />
                ) : (
                  <EmptyState text="暂无推荐结果" />
                )}
              </CardContent>
            </Card>

            <Card className="rounded-lg">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>学习路径</CardTitle>
                    <CardDescription>
                      PlannerAgent 产出的步骤化学习路径。
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    onClick={runLearningPath}
                    disabled={!diagnosis || activeAction === 'learning-path'}
                  >
                    {activeAction === 'learning-path' ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <BookOpenCheck className="size-4" />
                    )}
                    生成
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {learningPath ? (
                  <JsonBlock value={learningPath.learning_path} />
                ) : (
                  <EmptyState text="暂无学习路径" />
                )}
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </main>
  )
}
