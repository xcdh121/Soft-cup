import { useEffect, useMemo, useState } from 'react'
import {
  ActivityIcon,
  ArrowRightIcon,
  BookOpenCheckIcon,
  BrainCircuitIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleAlertIcon,
  Clock3Icon,
  DatabaseIcon,
  FileCheck2Icon,
  GitBranchIcon,
  GraduationCapIcon,
  HistoryIcon,
  Layers3Icon,
  LockKeyholeIcon,
  NetworkIcon,
  PlayIcon,
  RefreshCwIcon,
  RouteIcon,
  SearchIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TargetIcon,
  UserRoundSearchIcon,
  WrenchIcon,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'

type ToolRisk = 'read' | 'generate' | 'write'

type ToolExecution = {
  name: string
  summary: string
  duration: number
  evidence: number
  risk: ToolRisk
  icon: LucideIcon
}

type AgentExecution = {
  name: string
  role: string
  skill: string
  mode: string
  summary: string
  duration: number
  confidence: number
  evidence: number
  tone: 'blue' | 'cyan' | 'violet' | 'amber'
  icon: LucideIcon
  tools: Array<ToolExecution>
  gates: Array<string>
  warning?: string
}

const agents: Array<AgentExecution> = [
  {
    name: '画像智能体',
    role: '学习者画像',
    skill: '学习者证据采集',
    mode: '混合执行',
    summary: '整合学习偏好、目标与近期活动，确认当前画像数据完整且有效。',
    duration: 640,
    confidence: 94,
    evidence: 8,
    tone: 'blue',
    icon: UserRoundSearchIcon,
    tools: [
      {
        name: '读取学习者画像',
        summary: '获取学习目标、可用时间与偏好设置',
        duration: 126,
        evidence: 3,
        risk: 'read',
        icon: DatabaseIcon,
      },
      {
        name: '汇总反馈记录',
        summary: '归纳最近 14 天的 5 条有效反馈',
        duration: 184,
        evidence: 5,
        risk: 'read',
        icon: HistoryIcon,
      },
    ],
    gates: ['数据新鲜度小于 14 天', '关键画像字段完整'],
  },
  {
    name: '知识追踪智能体',
    role: '知识状态评估',
    skill: '学习者证据采集',
    mode: '确定性执行',
    summary: '识别 3 个薄弱知识点，其中“递归状态定义”掌握度最低。',
    duration: 820,
    confidence: 91,
    evidence: 18,
    tone: 'cyan',
    icon: NetworkIcon,
    tools: [
      {
        name: '查询知识状态',
        summary: '读取 12 个知识点的掌握度、趋势与置信度',
        duration: 213,
        evidence: 12,
        risk: 'read',
        icon: ActivityIcon,
      },
      {
        name: '读取近期练习',
        summary: '发现 6 次递归边界条件相关错误',
        duration: 276,
        evidence: 6,
        risk: 'read',
        icon: BookOpenCheckIcon,
      },
    ],
    gates: ['知识状态置信度达到阈值', '练习记录已去重'],
  },
  {
    name: '诊断智能体',
    role: '学习问题诊断',
    skill: '学习问题根因诊断',
    mode: '受控工具循环',
    summary: '主要障碍是递归状态定义不稳定，而非代码语法或执行环境问题。',
    duration: 1840,
    confidence: 82,
    evidence: 9,
    tone: 'violet',
    icon: BrainCircuitIcon,
    tools: [
      {
        name: '查询知识图谱',
        summary: '确认递归、栈与函数调用的先修依赖关系',
        duration: 318,
        evidence: 3,
        risk: 'read',
        icon: GitBranchIcon,
      },
      {
        name: '检索课程资料',
        summary: '找到 3 个与错误模式直接相关的证据片段',
        duration: 462,
        evidence: 3,
        risk: 'read',
        icon: SearchIcon,
      },
      {
        name: '读取近期练习',
        summary: '交叉验证 3 次同构题目的解题过程',
        duration: 241,
        evidence: 3,
        risk: 'read',
        icon: BookOpenCheckIcon,
      },
    ],
    gates: ['至少一条真实证据', '低证据不得输出高置信度结论'],
    warning: '置信度低于 85%，已保留补测建议',
  },
  {
    name: '规划智能体',
    role: '学习路径规划',
    skill: '个性化学习路径设计',
    mode: '混合执行',
    summary:
      '生成 3 步学习路径，先补状态定义，再练边界条件，最后完成迁移测验。',
    duration: 1270,
    confidence: 89,
    evidence: 7,
    tone: 'amber',
    icon: RouteIcon,
    tools: [
      {
        name: '获取可用学习资源',
        summary: '筛选出 4 项与目标和可用时长匹配的资源',
        duration: 236,
        evidence: 4,
        risk: 'read',
        icon: Layers3Icon,
      },
      {
        name: '生成学习路径草稿',
        summary: '创建含目标、预计时长和验收条件的 3 步草稿',
        duration: 594,
        evidence: 3,
        risk: 'generate',
        icon: SparklesIcon,
      },
    ],
    gates: ['先修关系正确', '总时长满足约束', '每一步包含验收条件'],
  },
]

const toneStyles = {
  blue: {
    icon: 'bg-blue-50 text-blue-700 ring-blue-100 dark:bg-blue-950/40 dark:text-blue-300 dark:ring-blue-900',
    border: 'border-blue-300 shadow-blue-950/5',
    soft: 'bg-blue-50/80 text-blue-800 dark:bg-blue-950/30 dark:text-blue-200',
  },
  cyan: {
    icon: 'bg-cyan-50 text-cyan-700 ring-cyan-100 dark:bg-cyan-950/40 dark:text-cyan-300 dark:ring-cyan-900',
    border: 'border-cyan-300 shadow-cyan-950/5',
    soft: 'bg-cyan-50/80 text-cyan-800 dark:bg-cyan-950/30 dark:text-cyan-200',
  },
  violet: {
    icon: 'bg-violet-50 text-violet-700 ring-violet-100 dark:bg-violet-950/40 dark:text-violet-300 dark:ring-violet-900',
    border: 'border-violet-300 shadow-violet-950/5',
    soft: 'bg-violet-50/80 text-violet-800 dark:bg-violet-950/30 dark:text-violet-200',
  },
  amber: {
    icon: 'bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900',
    border: 'border-amber-300 shadow-amber-950/5',
    soft: 'bg-amber-50/80 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200',
  },
} as const

const riskLabels: Record<ToolRisk, string> = {
  read: '只读',
  generate: '生成草稿',
  write: '写入',
}

const formatDuration = (duration: number) =>
  duration >= 1000 ? `${(duration / 1000).toFixed(1)} 秒` : `${duration} ms`

export function AgentRuntimePage() {
  const [activeAgent, setActiveAgent] = useState(2)
  const [showSkills, setShowSkills] = useState(true)
  const [expandedAgents, setExpandedAgents] = useState<Set<number>>(
    () => new Set([2]),
  )
  const [replayStep, setReplayStep] = useState<number | null>(null)

  useEffect(() => {
    if (replayStep === null) return
    if (replayStep >= agents.length) {
      const doneTimer = window.setTimeout(() => setReplayStep(null), 700)
      return () => window.clearTimeout(doneTimer)
    }
    const timer = window.setTimeout(() => {
      setActiveAgent(replayStep)
      setExpandedAgents(new Set([replayStep]))
      setReplayStep((step) => (step === null ? null : step + 1))
    }, 850)
    return () => window.clearTimeout(timer)
  }, [replayStep])

  const totalDuration = useMemo(
    () => agents.reduce((sum, agent) => sum + agent.duration, 0),
    [],
  )
  const totalTools = useMemo(
    () => agents.reduce((sum, agent) => sum + agent.tools.length, 0),
    [],
  )
  const isReplaying = replayStep !== null
  const completedDuringReplay = replayStep ?? agents.length

  const toggleAgent = (index: number) => {
    setActiveAgent(index)
    setExpandedAgents((current) => {
      const next = new Set(current)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  return (
    <div className="flex min-h-full flex-col bg-[linear-gradient(180deg,var(--background)_0%,color-mix(in_srgb,var(--muted)_38%,var(--background))_100%)]">
      <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center border-b bg-background/90 px-3 backdrop-blur-md">
        <div className="flex flex-1 items-center gap-2">
          <SidebarTrigger />
          <Separator
            orientation="vertical"
            className="mx-1 data-[orientation=vertical]:h-4"
          />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage className="font-medium">
                  智能协作观测台
                </BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-50" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
          </span>
          运行数据已脱敏
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1480px] flex-1 space-y-6 p-4 md:p-6 xl:p-8">
        <section className="relative overflow-hidden rounded-3xl bg-[#061a3a] px-5 py-6 text-white shadow-xl shadow-[#052659]/10 md:px-8 md:py-8">
          <div className="absolute -right-24 -top-28 size-72 rounded-full bg-cyan-400/15 blur-3xl" />
          <div className="absolute -bottom-40 left-1/3 size-80 rounded-full bg-blue-500/20 blur-3xl" />
          <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="border border-emerald-300/20 bg-emerald-400/15 text-emerald-100">
                  <CheckCircle2Icon /> 运行已完成
                </Badge>
                <span className="font-mono text-xs text-blue-200/70">
                  RUN · 20260713-0842
                </span>
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight md:text-4xl">
                  个性化学习路径生成
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-blue-100/75 md:text-base">
                  总控智能体根据“掌握递归基础并完成迁移练习”的目标，协调 4
                  个智能体完成证据采集、根因诊断与路径规划。
                </p>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-blue-100/65">
                <span className="inline-flex items-center gap-1.5">
                  <TargetIcon className="size-3.5" />
                  目标：递归与调用栈
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Clock3Icon className="size-3.5" />
                  用时 {formatDuration(totalDuration)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <ShieldCheckIcon className="size-3.5" />
                  全链路审计开启
                </span>
              </div>
            </div>
            <Button
              variant="secondary"
              className="w-full bg-white/10 text-white ring-1 ring-white/20 hover:bg-white/20 hover:text-white sm:w-auto"
              disabled={isReplaying}
              onClick={() => {
                setReplayStep(0)
                setExpandedAgents(new Set())
              }}
            >
              {isReplaying ? (
                <RefreshCwIcon className="animate-spin" />
              ) : (
                <PlayIcon />
              )}
              {isReplaying ? '正在回放' : '回放执行过程'}
            </Button>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: '参与智能体',
              value: '4',
              suffix: '个',
              icon: BrainCircuitIcon,
              note: '由总控智能体编排',
            },
            {
              label: '能力执行',
              value: '4',
              suffix: '项',
              icon: SparklesIcon,
              note: '全部通过质量门',
            },
            {
              label: '工具调用',
              value: String(totalTools),
              suffix: '次',
              icon: WrenchIcon,
              note: '0 次越权或超时',
            },
            {
              label: '引用证据',
              value: '42',
              suffix: '条',
              icon: FileCheck2Icon,
              note: '结果均可追溯',
            },
          ].map((metric) => (
            <div
              key={metric.label}
              className="flex items-center gap-4 rounded-2xl border bg-card/90 p-4 shadow-sm"
            >
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/5 text-primary ring-1 ring-primary/10">
                <metric.icon className="size-5" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-muted-foreground">
                  {metric.label}
                </div>
                <div className="mt-0.5 flex items-baseline gap-1">
                  <span className="text-2xl font-semibold tracking-tight">
                    {metric.value}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {metric.suffix}
                  </span>
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {metric.note}
                </div>
              </div>
            </div>
          ))}
        </section>

        <section className="rounded-3xl border bg-card/90 p-5 shadow-sm md:p-6">
          <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
            <div>
              <div className="flex items-center gap-2 text-lg font-semibold">
                <RouteIcon className="size-5 text-primary" />
                协作主流程
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                点击智能体查看其能力与工具执行详情
              </p>
            </div>
            <Badge variant="outline" className="bg-background">
              <GitBranchIcon />
              规则路由 · 受控执行
            </Badge>
          </div>

          <div className="relative grid gap-3 md:grid-cols-4">
            <div className="absolute left-[12.5%] right-[12.5%] top-7 hidden border-t border-dashed border-primary/25 md:block" />
            {agents.map((agent, index) => {
              const AgentIcon = agent.icon
              const isActive = activeAgent === index
              const isRunning = isReplaying && replayStep === index + 1
              const isPending = isReplaying && index >= completedDuringReplay
              return (
                <button
                  type="button"
                  key={agent.name}
                  onClick={() => toggleAgent(index)}
                  className={cn(
                    'relative z-10 flex min-w-0 flex-row items-center gap-3 rounded-2xl border bg-card p-3 text-left transition-all hover:-translate-y-0.5 hover:shadow-md md:flex-col md:items-start md:p-4',
                    isActive ? toneStyles[agent.tone].border : 'border-border',
                    isPending && 'opacity-45',
                  )}
                >
                  <div
                    className={cn(
                      'flex size-11 shrink-0 items-center justify-center rounded-xl ring-4',
                      toneStyles[agent.tone].icon,
                    )}
                  >
                    {isRunning ? (
                      <RefreshCwIcon className="size-5 animate-spin" />
                    ) : (
                      <AgentIcon className="size-5" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="truncate font-medium">{agent.name}</div>
                      {!isPending && !isRunning && (
                        <CheckCircle2Icon className="size-4 shrink-0 text-emerald-600" />
                      )}
                    </div>
                    <div className="mt-1 truncate text-xs text-muted-foreground">
                      {agent.skill}
                    </div>
                  </div>
                  {index < agents.length - 1 && (
                    <ArrowRightIcon className="absolute -right-3 top-5 hidden size-3.5 rounded-full bg-card text-primary/50 md:block" />
                  )}
                </button>
              )
            })}
          </div>
          {isReplaying && (
            <Progress
              className="mt-5 h-1.5"
              value={(completedDuringReplay / agents.length) * 100}
            />
          )}
        </section>

        <section className="overflow-hidden rounded-3xl border bg-card/90 shadow-sm">
          <button
            type="button"
            className="flex w-full items-start gap-3 p-5 text-left md:items-center md:p-6"
            onClick={() => setShowSkills((visible) => !visible)}
            aria-expanded={showSkills}
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-700 ring-1 ring-violet-100 dark:bg-violet-950/40 dark:text-violet-300 dark:ring-violet-900">
              <Layers3Icon className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold">本次使用的 Skill</h2>
                <Badge
                  variant="outline"
                  className="border-violet-200 bg-violet-50/70 text-violet-700 dark:bg-violet-950/30 dark:text-violet-200"
                >
                  3 项实际能力
                </Badge>
              </div>
              <p className="mt-1 text-sm leading-5 text-muted-foreground">
                直接展示每项能力解决什么问题、参考什么证据，以及交付什么结果
              </p>
            </div>
            <ChevronDownIcon
              className={cn(
                'mt-1 size-4 shrink-0 text-muted-foreground transition-transform md:mt-0',
                showSkills && 'rotate-180',
              )}
            />
          </button>

          {showSkills && (
            <div className="border-t bg-muted/15 p-5 md:p-6">
              <div className="grid gap-4 xl:grid-cols-3">
                {[
                  {
                    name: '学习者证据采集',
                    mode: '混合能力',
                    owners: '画像智能体 · 知识追踪智能体',
                    description:
                      '把分散的学习画像、知识状态、练习表现和反馈汇总成一份可追溯的学习证据快照。',
                    evidence: [
                      '学习目标与偏好',
                      '知识点掌握度',
                      '近期练习与反馈',
                    ],
                    outputs: [
                      '画像摘要',
                      '知识状态摘要',
                      '证据引用',
                      '数据缺口',
                    ],
                    gate: '关键字段完整，数据新鲜度满足要求',
                    icon: UserRoundSearchIcon,
                    tone: 'blue',
                  },
                  {
                    name: '学习问题根因诊断',
                    mode: '推理能力',
                    owners: '诊断智能体',
                    description:
                      '从薄弱知识点出发，结合错误模式、先修关系和教材依据，区分表象错误与真正学习障碍。',
                    evidence: [
                      '薄弱知识点',
                      '同类错误模式',
                      '先修图谱与课程材料',
                    ],
                    outputs: ['根因候选', '支持证据', '置信度', '补测建议'],
                    gate: '至少一条真实证据，证据不足时降低置信度',
                    icon: BrainCircuitIcon,
                    tone: 'violet',
                  },
                  {
                    name: '个性化学习路径设计',
                    mode: '规划能力',
                    owners: '规划智能体',
                    description:
                      '根据诊断结论、先修关系、可用时间和已有资源，生成可以执行和验收的学习步骤。',
                    evidence: [
                      '诊断结论',
                      '知识先修关系',
                      '时间约束与可用资源',
                    ],
                    outputs: [
                      '有序学习步骤',
                      '阶段目标',
                      '预计时长',
                      '验收条件',
                    ],
                    gate: '先修顺序正确，总时长满足约束，每步可验收',
                    icon: RouteIcon,
                    tone: 'amber',
                  },
                ].map((skill) => {
                  const SkillIcon = skill.icon
                  const style =
                    toneStyles[skill.tone as keyof typeof toneStyles]
                  return (
                    <article
                      key={skill.name}
                      className="flex h-full flex-col rounded-2xl border bg-background p-4 md:p-5"
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

              <div className="mt-4 rounded-xl border border-dashed bg-background/70 p-4">
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

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="space-y-3">
            <div className="flex items-end justify-between px-1">
              <div>
                <h2 className="text-lg font-semibold">执行时间线</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  仅展示结果摘要、证据数量和安全状态
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="hidden sm:inline-flex"
                onClick={() =>
                  setExpandedAgents(
                    expandedAgents.size === agents.length
                      ? new Set()
                      : new Set(agents.map((_, index) => index)),
                  )
                }
              >
                {expandedAgents.size === agents.length
                  ? '全部收起'
                  : '全部展开'}
              </Button>
            </div>

            {agents.map((agent, index) => {
              const AgentIcon = agent.icon
              const expanded = expandedAgents.has(index)
              const style = toneStyles[agent.tone]
              return (
                <article
                  key={agent.name}
                  className={cn(
                    'overflow-hidden rounded-2xl border bg-card shadow-sm transition-shadow',
                    activeAgent === index && style.border,
                  )}
                >
                  <button
                    type="button"
                    className="flex w-full items-start gap-3 p-4 text-left md:p-5"
                    onClick={() => toggleAgent(index)}
                    aria-expanded={expanded}
                  >
                    <div
                      className={cn(
                        'flex size-10 shrink-0 items-center justify-center rounded-xl ring-4',
                        style.icon,
                      )}
                    >
                      <AgentIcon className="size-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold">{agent.name}</h3>
                        <Badge variant="secondary" className={style.soft}>
                          能力 · {agent.skill}
                        </Badge>
                        {agent.warning && (
                          <Badge
                            variant="outline"
                            className="border-amber-300 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
                          >
                            <CircleAlertIcon />
                            需关注
                          </Badge>
                        )}
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
                        <div className="rounded-xl border bg-background p-4">
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
                  )}
                </article>
              )
            })}
          </section>

          <aside className="space-y-4 xl:sticky xl:top-20">
            <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
              <div className="border-b bg-primary/[0.035] p-5">
                <div className="flex items-center gap-2 font-semibold">
                  <ShieldCheckIcon className="size-5 text-emerald-600" />
                  ToolRunner 安全闸门
                </div>
                <p className="mt-1.5 text-sm leading-5 text-muted-foreground">
                  每次内部工具调用都通过统一校验与审计
                </p>
              </div>
              <div className="p-5">
                <div className="space-y-0">
                  {[
                    ['身份与项目权限', '已通过'],
                    ['Agent 工具白名单', '已通过'],
                    ['参数结构校验', '已通过'],
                    ['超时与幂等控制', '已启用'],
                    ['结果过滤与脱敏', '已完成'],
                    ['审计事件写入', '9 / 9'],
                  ].map(([label, value], index) => (
                    <div
                      key={label}
                      className="relative flex items-center gap-3 pb-4 last:pb-0"
                    >
                      {index < 5 && (
                        <div className="absolute bottom-0 left-[7px] top-4 border-l border-dashed border-border" />
                      )}
                      <CheckCircle2Icon className="z-10 size-4 shrink-0 bg-card text-emerald-600" />
                      <span className="min-w-0 flex-1 text-sm">{label}</span>
                      <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border bg-card p-5 shadow-sm">
              <div className="flex items-center gap-2 font-semibold">
                <ActivityIcon className="size-5 text-primary" />
                运行约束
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {[
                  ['最大工具调用', '6 次'],
                  ['Skill 超时', '60 秒'],
                  ['单工具超时', '15 秒'],
                  ['写操作', '需确认'],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl bg-muted/45 p-3">
                    <div className="text-[11px] text-muted-foreground">
                      {label}
                    </div>
                    <div className="mt-1 text-sm font-semibold">{value}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-xs leading-5 text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-100">
                <LockKeyholeIcon className="mt-0.5 size-4 shrink-0" />
                <span>
                  用户身份、项目权限和运行上下文由服务端注入，模型无法自行指定。
                </span>
              </div>
            </section>

            <section className="rounded-2xl border border-dashed bg-card/60 p-4">
              <div className="flex gap-3">
                <GraduationCapIcon className="mt-0.5 size-5 shrink-0 text-primary" />
                <div>
                  <div className="text-sm font-medium">
                    学生可理解，系统可审计
                  </div>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    页面不会展示系统
                    Prompt、模型思维链、完整工具参数、密钥或内部错误堆栈。
                  </p>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </main>
    </div>
  )
}
