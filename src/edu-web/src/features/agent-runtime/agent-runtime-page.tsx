import { Result, useAtomValue } from '@effect-atom/atom-react'
import { useEffect, useMemo, useState } from 'react'
import {
  ActivityIcon,
  BanIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  Clock3Icon,
  CoinsIcon,
  DatabaseIcon,
  PlayIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  WifiIcon,
} from 'lucide-react'
import { getPlannerExecution } from './planner-execution'
import type { AgentRunStatus } from '@/data-acess/agent-runs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { agentRunsApi } from '@/data-acess/agent-runs'
import { projectsAtom } from '@/data-acess/project'
import { useAgentRun } from '@/hooks/use-agent-run'

const lastProjectStorageKey = 'agent-runtime:last-project-id'

const replaceRunSearch = (projectId: string, runId: string | null) => {
  const search = new URLSearchParams(window.location.search)
  search.set('projectId', projectId)
  if (runId) search.set('runId', runId)
  else search.delete('runId')
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}?${search.toString()}`,
  )
}

const labels: Record<AgentRunStatus | 'skipped', string> = {
  queued: '排队中',
  pending: '待执行',
  running: '正在执行',
  waiting_external: '等待外部生成',
  partially_completed: '部分完成',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
  skipped: '已跳过',
}

const terminal = new Set<AgentRunStatus>([
  'completed',
  'partially_completed',
  'cancelled',
  'failed',
])

export function AgentRuntimePage() {
  const params = new URLSearchParams(window.location.search)
  const demoMode = params.get('demoMode') === 'true'
  const [projectId, setProjectId] = useState(params.get('projectId') ?? '')
  const [runId, setRunId] = useState<string | null>(params.get('runId'))
  const [goal, setGoal] = useState('diagnosis')
  const [busy, setBusy] = useState(false)
  const [restoringLatest, setRestoringLatest] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const projectsResult = useAtomValue(projectsAtom)
  const projects = Result.isSuccess(projectsResult) ? projectsResult.value : []
  const { run, steps, events, error, connection, refresh } = useAgentRun(runId)
  const activeRun = run?.project_id === projectId ? run : null

  useEffect(() => {
    if (!projectId && projects.length > 0) {
      const storedProjectId = window.localStorage.getItem(lastProjectStorageKey)
      const nextProjectId =
        projects.find((project) => project.id === storedProjectId)?.id ??
        projects[0].id
      setProjectId(nextProjectId)
    }
  }, [projectId, projects])

  useEffect(() => {
    if (!projectId) return
    window.localStorage.setItem(lastProjectStorageKey, projectId)
  }, [projectId])

  useEffect(() => {
    if (!projectId || runId || demoMode) return
    let active = true
    setRestoringLatest(true)
    setStartError(null)
    void agentRunsApi
      .latest(projectId)
      .then((latest) => {
        if (!active || !latest) return
        setRunId(latest.run_id)
        replaceRunSearch(projectId, latest.run_id)
      })
      .catch((cause: unknown) => {
        if (!active) return
        setStartError(
          cause instanceof Error
            ? cause.message
            : '恢复最近一次运行失败，请稍后重试。',
        )
      })
      .finally(() => {
        if (active) setRestoringLatest(false)
      })
    return () => {
      active = false
    }
  }, [demoMode, projectId, runId])

  const completed = steps.filter((step) =>
    ['completed', 'skipped'].includes(step.status),
  ).length
  const progress = steps.length
    ? Math.round((completed / steps.length) * 100)
    : 0
  const evidenceCount = useMemo(
    () =>
      events.reduce(
        (total, event) => total + Number(event.payload.evidence_count ?? 0),
        0,
      ),
    [events],
  )
  const totalTokens =
    (activeRun?.input_tokens ?? 0) + (activeRun?.output_tokens ?? 0)
  const tokenDisplay = totalTokens
    ? totalTokens.toLocaleString('zh-CN')
    : activeRun?.model_name
      ? '未采集'
      : '未调用模型'
  const plannerExecution = useMemo(
    () => getPlannerExecution(activeRun, events),
    [activeRun, events],
  )

  const start = async () => {
    if (!projectId.trim()) return
    setBusy(true)
    setStartError(null)
    try {
      const created = await agentRunsApi.create(projectId.trim(), goal)
      setRunId(created.run_id)
      replaceRunSearch(projectId.trim(), created.run_id)
    } catch (cause) {
      setStartError(
        cause instanceof Error ? cause.message : '创建智能体运行失败，请稍后重试。',
      )
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    if (!runId) return
    await agentRunsApi.cancel(runId)
    await refresh()
  }

  const retry = async () => {
    if (!runId) return
    const created = await agentRunsApi.retry(runId)
    setRunId(created.run_id)
    replaceRunSearch(projectId, created.run_id)
  }

  return (
    <div className="min-h-screen bg-muted/20" data-testid="agent-runtime-page">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex h-16 items-center gap-3 px-4 md:px-6">
          <SidebarTrigger />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">智能协作观测台</h1>
            <p className="text-xs text-muted-foreground">
              查看 AI 如何协作完成诊断、推荐与学习路径，并审计每一步依据
            </p>
          </div>
          {demoMode ? (
            <Badge
              variant="outline"
              className="border-amber-400 text-amber-700"
            >
              演示模式 · 独立数据源
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="border-emerald-400 text-emerald-700"
            >
              真实运行
            </Badge>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
        <section className="rounded-2xl border border-primary/15 bg-primary/[0.04] p-5">
          <h2 className="font-semibold">这里不是新的学习模块，而是 AI 执行记录</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            选择一个学习目标后，系统会创建真实的多智能体任务。你可以查看画像、知识追踪、诊断、资源和规划等节点如何协作，以及证据、耗时、模型 Token、失败兜底和重试情况。
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            多智能体完整运行不限制次数；模型 Token 与耗时仍会按次记录，方便核对执行成本和效果。
          </p>
        </section>

        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">项目</span>
              <select
                data-testid="project-id-input"
                className="h-10 w-full rounded-md border bg-background px-3"
                value={projectId}
                onChange={(event) => {
                  const nextProjectId = event.target.value
                  setProjectId(nextProjectId)
                  setRunId(null)
                  replaceRunSearch(nextProjectId, null)
                }}
                disabled={projects.length === 0}
              >
                {projects.length === 0 && (
                  <option value="">暂无可用项目</option>
                )}
                {projectId &&
                  !projects.some((project) => project.id === projectId) && (
                    <option value={projectId}>
                      当前项目（{projectId.slice(0, 8)}…）
                    </option>
                  )}
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}（{project.id.slice(0, 8)}…）
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">运行目标</span>
              <select
                data-testid="run-goal-select"
                className="h-10 w-full rounded-md border bg-background px-3"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
              >
                <option value="diagnosis">学习诊断</option>
                <option value="recommendations">资源推荐</option>
                <option value="learning_path">学习路径</option>
              </select>
            </label>
            <Button
              data-testid="start-run-button"
              className="self-end"
              disabled={!projectId.trim() || busy || demoMode}
              onClick={() => void start()}
            >
              {busy ? <RefreshCwIcon className="animate-spin" /> : <PlayIcon />}
              创建真实运行
            </Button>
          </div>
          {startError && (
            <div className="mt-4 flex gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <CircleAlertIcon className="mt-0.5 size-4 shrink-0" />
              {startError}
            </div>
          )}
        </section>

        {!activeRun && !demoMode && !restoringLatest && (
          <section className="rounded-2xl border border-dashed bg-card p-10 text-center">
            <DatabaseIcon className="mx-auto size-9 text-muted-foreground" />
            <h2 className="mt-3 font-semibold">尚未选择真实运行</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              选择项目创建运行，或在地址中提供 runId
              查看已有运行。页面不会播放假进度。
            </p>
          </section>
        )}

        {error && (
          <div className="flex gap-2 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            <CircleAlertIcon className="size-4" />
            {error}；系统正在按最后事件序号重连。
          </div>
        )}

        {activeRun && (
          <>
            <section
              className="rounded-2xl border bg-card p-5 shadow-sm"
              data-testid="run-summary"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">运行 {activeRun.run_id}</h2>
                    <Badge>{labels[activeRun.status]}</Badge>
                    <Badge variant="outline">
                      {activeRun.orchestration_version}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    当前节点：{activeRun.current_agent_name ?? '无'} · Trace：
                    {activeRun.trace_id ?? '—'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {!terminal.has(activeRun.status) && (
                    <Button variant="outline" onClick={() => void cancel()}>
                      <BanIcon /> 取消
                    </Button>
                  )}
                  {['failed', 'cancelled', 'partially_completed'].includes(
                    activeRun.status,
                  ) && (
                    <Button onClick={() => void retry()}>
                      <RotateCcwIcon /> 从失败节点重试
                    </Button>
                  )}
                </div>
              </div>
              <Progress className="mt-5" value={progress} />
              <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                <span>
                  {completed} / {steps.length} 个步骤
                </span>
                <span className="inline-flex items-center gap-1">
                  <WifiIcon className="size-3" /> {connection}
                </span>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {[
                  [
                    Clock3Icon,
                    '耗时',
                    activeRun.duration_ms
                      ? `${activeRun.duration_ms} ms`
                      : '进行中',
                  ],
                  [ActivityIcon, '证据', `${evidenceCount} 条`],
                  [CoinsIcon, 'Token', tokenDisplay],
                ].map(([Icon, label, value]) => {
                  const MetricIcon = Icon as typeof Clock3Icon
                  return (
                    <article
                      key={String(label)}
                      className="rounded-xl border bg-background p-3"
                    >
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <MetricIcon className="size-3.5" />
                        {String(label)}
                      </div>
                      <div className="mt-1 font-semibold">{String(value)}</div>
                    </article>
                  )
                })}
              </div>
            </section>

            <section className="space-y-3" data-testid="run-steps">
              {steps.map((step, index) => {
                const latestEvent = [...events]
                  .reverse()
                  .find((event) => event.agent_name === step.agent_name)
                return (
                  <article
                    key={step.step_id}
                    className="rounded-xl border bg-card p-4 shadow-sm"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                        {index + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-medium">{step.agent_name}</h3>
                          <Badge variant="outline">{labels[step.status]}</Badge>
                          {step.optional && (
                            <Badge variant="secondary">非关键节点</Badge>
                          )}
                        </div>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          {latestEvent?.summary ?? '等待该节点产生真实事件。'}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <Clock3Icon className="size-3.5" />
                            {step.duration_ms == null
                              ? '—'
                              : `${step.duration_ms} ms`}
                          </span>
                          <span>
                            尝试 {step.attempt_count} / {step.max_attempts}
                          </span>
                          {step.error_code && <span>{step.error_code}</span>}
                        </div>
                        {step.agent_name === 'PlannerAgent' && (
                          <div
                            className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs"
                            data-testid="planner-model-usage"
                          >
                            <Badge
                              variant={
                                plannerExecution.mode === 'llm'
                                  ? 'default'
                                  : 'secondary'
                              }
                            >
                              {plannerExecution.mode === 'llm'
                                ? '模型生成'
                                : plannerExecution.mode === 'rule_fallback'
                                  ? '规则降级'
                                  : step.status === 'running'
                                    ? '正在执行'
                                    : '等待执行'}
                            </Badge>
                            <span>
                              模型：{plannerExecution.modelName ?? '—'}
                            </span>
                            <span>
                              Token：
                              {plannerExecution.inputTokens +
                                plannerExecution.outputTokens >
                              0
                                ? `${(
                                    plannerExecution.inputTokens +
                                    plannerExecution.outputTokens
                                  ).toLocaleString('zh-CN')}（输入 ${plannerExecution.inputTokens.toLocaleString('zh-CN')} / 输出 ${plannerExecution.outputTokens.toLocaleString('zh-CN')}）`
                                : '—'}
                            </span>
                          </div>
                        )}
                      </div>
                      {step.status === 'completed' && (
                        <CheckCircle2Icon className="size-5 text-emerald-600" />
                      )}
                    </div>
                  </article>
                )
              })}
            </section>

            <section className="rounded-2xl border bg-card p-5 shadow-sm">
              <h2 className="font-semibold">可解释事件摘要</h2>
              <div className="mt-3 space-y-3">
                {events.slice(-8).map((event) => (
                  <div
                    key={event.sequence}
                    className="grid grid-cols-[56px_1fr] gap-3 text-sm"
                  >
                    <span className="font-mono text-xs text-muted-foreground">
                      #{event.sequence}
                    </span>
                    <div>
                      <div className="font-medium">
                        {event.agent_name ?? '运行时'} · {event.event_type}
                      </div>
                      <p className="mt-0.5 text-muted-foreground">
                        {event.summary}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
