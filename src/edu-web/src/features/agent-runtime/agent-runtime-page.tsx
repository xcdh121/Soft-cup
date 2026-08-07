import { useMemo, useState } from 'react'
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
  ShieldCheckIcon,
  WifiIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { agentRunsApi, type AgentRunStatus } from '@/data-acess/agent-runs'
import { useAgentRun } from '@/hooks/use-agent-run'

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
  const { run, steps, events, error, connection, refresh } = useAgentRun(runId)

  const completed = steps.filter((step) =>
    ['completed', 'skipped'].includes(step.status),
  ).length
  const progress = steps.length ? Math.round((completed / steps.length) * 100) : 0
  const evidenceCount = useMemo(
    () =>
      events.reduce(
        (total, event) =>
          total + Number(event.payload.evidence_count ?? 0),
        0,
      ),
    [events],
  )

  const start = async () => {
    if (!projectId.trim()) return
    setBusy(true)
    try {
      const created = await agentRunsApi.create(projectId.trim(), goal)
      setRunId(created.run_id)
      window.history.replaceState(
        null,
        '',
        `?projectId=${encodeURIComponent(projectId.trim())}&runId=${encodeURIComponent(created.run_id)}`,
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
    window.history.replaceState(null, '', `?projectId=${projectId}&runId=${created.run_id}`)
  }

  return (
    <div className="min-h-screen bg-muted/20" data-testid="agent-runtime-page">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex h-16 items-center gap-3 px-4 md:px-6">
          <SidebarTrigger />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">智能协作观测台</h1>
            <p className="text-xs text-muted-foreground">
              数据库事件为事实源，刷新后从最后事件继续
            </p>
          </div>
          {demoMode ? (
            <Badge variant="outline" className="border-amber-400 text-amber-700">
              演示模式 · 独立数据源
            </Badge>
          ) : (
            <Badge variant="outline" className="border-emerald-400 text-emerald-700">
              真实运行
            </Badge>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">项目 ID</span>
              <input
                data-testid="project-id-input"
                className="h-10 w-full rounded-md border bg-background px-3"
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                placeholder="输入有权限的项目 ID"
              />
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
        </section>

        {!run && !demoMode && (
          <section className="rounded-2xl border border-dashed bg-card p-10 text-center">
            <DatabaseIcon className="mx-auto size-9 text-muted-foreground" />
            <h2 className="mt-3 font-semibold">尚未选择真实运行</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              输入项目 ID 创建运行，或在地址中提供 runId 查看已有运行。页面不会播放假进度。
            </p>
          </section>
        )}

        {error && (
          <div className="flex gap-2 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            <CircleAlertIcon className="size-4" />
            {error}；系统正在按最后事件序号重连。
          </div>
        )}

        {run && (
          <>
            <section className="rounded-2xl border bg-card p-5 shadow-sm" data-testid="run-summary">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">运行 {run.run_id}</h2>
                    <Badge>{labels[run.status]}</Badge>
                    <Badge variant="outline">{run.orchestration_version}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    当前节点：{run.current_agent_name ?? '无'} · Trace：{run.trace_id ?? '—'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {!terminal.has(run.status) && (
                    <Button variant="outline" onClick={() => void cancel()}>
                      <BanIcon /> 取消
                    </Button>
                  )}
                  {['failed', 'cancelled', 'partially_completed'].includes(run.status) && (
                    <Button onClick={() => void retry()}>
                      <RotateCcwIcon /> 从失败节点重试
                    </Button>
                  )}
                </div>
              </div>
              <Progress className="mt-5" value={progress} />
              <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                <span>{completed} / {steps.length} 个步骤</span>
                <span className="inline-flex items-center gap-1">
                  <WifiIcon className="size-3" /> {connection}
                </span>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-4">
                {[
                  [Clock3Icon, '耗时', run.duration_ms ? `${run.duration_ms} ms` : '进行中'],
                  [ActivityIcon, '证据', `${evidenceCount} 条`],
                  [CoinsIcon, 'Token', `${run.input_tokens + run.output_tokens}`],
                  [ShieldCheckIcon, '估算成本', `¥${(run.estimated_cost_micros / 1_000_000).toFixed(4)}`],
                ].map(([Icon, label, value]) => {
                  const MetricIcon = Icon as typeof Clock3Icon
                  return (
                    <article
                      key={skill.name}
                      className="flex h-full flex-col rounded-2xl border bg-card p-4 text-card-foreground md:p-5"
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            'flex size-10 shrink-0 items-center justify-center rounded-xl ring-4',
                            style.icon,
                          )}
                        >
                          <SkillIcon className="size-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold">{skill.name}</h3>
                            <Badge variant="outline">{skill.mode}</Badge>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {skill.owners}
                          </div>
                        </div>
                      </div>

                      <p className="mt-4 text-sm leading-6 text-muted-foreground">
                        {skill.description}
                      </p>

                      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                        <div>
                          <div className="text-xs font-medium text-foreground">
                            参考信息
                          </div>
                          <ul className="mt-2 space-y-1.5">
                            {skill.evidence.map((item) => (
                              <li
                                key={item}
                                className="flex gap-2 text-xs leading-5 text-muted-foreground"
                              >
                                <DatabaseIcon className="mt-1 size-3 shrink-0" />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-foreground">
                            能力产出
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {skill.outputs.map((item) => (
                              <span
                                key={item}
                                className={cn(
                                  'rounded-md px-2 py-1 text-[11px]',
                                  style.soft,
                                )}
                              >
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 flex gap-2 border-t pt-3 text-xs leading-5">
                        <ShieldCheckIcon className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                        <span>
                          <span className="font-medium">质量要求：</span>
                          <span className="text-muted-foreground">
                            {skill.gate}
                          </span>
                        </span>
                      </div>
                    </article>
                  )
                })}
              </div>

              <div className="mt-4 rounded-xl border border-dashed bg-card/80 p-4 text-card-foreground">
                <div className="flex items-center gap-2 text-xs font-medium text-foreground">
                  <ShieldCheckIcon className="size-4 text-emerald-600" />
                  Harness 运行保障
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                  {[
                    '权限与上下文由服务端注入',
                    '最多 6 次工具操作',
                    '60 秒能力超时',
                    '输出结构校验',
                    '失败自动回退',
                    '全过程审计',
                  ].map((item) => (
                    <span
                      key={item}
                      className="rounded-md border bg-card px-2.5 py-1.5"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
          </section>

        <section className="space-y-3" data-testid="run-steps">
          {steps.map((step, index) => (
            <article key={step.step_id} className="rounded-xl border bg-card p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{index + 1}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium">{step.agent_name}</h3>
                    <Badge variant="outline">{labels[step.status]}</Badge>
                    {step.optional && <Badge variant="secondary">非关键节点</Badge>}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {agent.summary}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <Clock3Icon className="size-3.5" />
                      {formatDuration(agent.duration)}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <FileCheck2Icon className="size-3.5" />
                      {agent.evidence} 条证据
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <ActivityIcon className="size-3.5" />
                      置信度 {agent.confidence}%
                    </span>
                  </div>
                </div>
                <ChevronDownIcon
                  className={cn(
                    'mt-1 size-4 shrink-0 text-muted-foreground transition-transform',
                    expanded && 'rotate-180',
                  )}
                />
              </button>

              {expanded && (
                <div className="border-t bg-muted/15 px-4 py-5 md:px-5">
                  {agent.warning && (
                    <div className="mb-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
                      <CircleAlertIcon className="mt-0.5 size-4 shrink-0" />
                      <span>
                        {agent.warning}，不会将不确定判断包装成确定结论。
                      </span>
                    </div>
                  )}
                  <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_240px]">
                    <div>
                      <div className="mb-3 flex items-center justify-between">
                        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          工具行动记录
                        </div>
                        <Badge variant="outline">{agent.mode}</Badge>
                      </div>
                      <div className="relative space-y-1 before:absolute before:bottom-5 before:left-[17px] before:top-5 before:border-l before:border-dashed before:border-border">
                        {agent.tools.map((tool) => {
                          const ToolIcon = tool.icon
                          return (
                            <div
                              key={tool.name}
                              className="relative flex gap-3 rounded-xl p-2.5 transition-colors hover:bg-background"
                            >
                              <div className="z-10 flex size-9 shrink-0 items-center justify-center rounded-full border bg-background text-primary">
                                <ToolIcon className="size-4" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-sm font-medium">
                                    {tool.name}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      'h-5 px-1.5 font-normal',
                                      tool.risk === 'generate' &&
                                      'border-violet-200 bg-violet-50 text-violet-700 dark:bg-violet-950/30 dark:text-violet-200',
                                    )}
                                  >
                                    {riskLabels[tool.risk]}
                                  </Badge>
                                  <CheckCircle2Icon className="size-3.5 text-emerald-600" />
                                </div>
                                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                  {tool.summary}
                                </p>
                                <div className="mt-1.5 flex gap-3 text-[11px] text-muted-foreground">
                                  <span>{tool.evidence} 条证据</span>
                                  <span>{tool.duration} ms</span>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                    <div className="rounded-xl border bg-card p-4 text-card-foreground">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <ShieldCheckIcon className="size-4 text-emerald-600" />
                        质量门
                      </div>
                      <div className="mt-3 space-y-2.5">
                        {agent.gates.map((gate) => (
                          <div
                            key={gate}
                            className="flex gap-2 text-xs leading-5"
                          >
                            <CheckCircle2Icon className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                            <span>{gate}</span>
                          </div>
                        ))}
                      </div>
                      <Separator className="my-3" />
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">
                          回退策略
                        </span>
                        <span className="font-medium">未触发</span>
                      </div>
                    </div>
                  </div>
                </div>
                    {step.status === 'completed' && <CheckCircle2Icon className="size-5 text-emerald-600" />}
            </div>
                </article>
              ))}
      </section>

      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <h2 className="font-semibold">可解释事件摘要</h2>
        <div className="mt-3 space-y-3">
          {events.slice(-8).map((event) => (
            <div key={event.sequence} className="grid grid-cols-[56px_1fr] gap-3 text-sm">
              <span className="font-mono text-xs text-muted-foreground">#{event.sequence}</span>
              <div>
                <div className="font-medium">{event.agent_name ?? '运行时'} · {event.event_type}</div>
                <p className="mt-0.5 text-muted-foreground">{event.summary}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}
      </main >
    </div >
  )
}
