import { CheckIcon, Loader2Icon } from 'lucide-react'
import type { AgentRunEvent } from '@/data-acess/agent-runs'

const stages = [
  ['SupervisorAgent', '总控编排', '理解问题并确定受约束协作链路'],
  ['ProfileAgent', '学习者画像', '读取学习目标、偏好与进度证据'],
  ['KTAgent', '知识状态评估', '根据真实学习证据更新知识状态'],
  ['DiagnosisAgent', '学习诊断', '比较多项根因与证据/反证'],
  ['ResourceAgent', '资源规划', '检索、排序并调度学习资源'],
  ['PlannerAgent', '学习路径规划', '按先修关系与时间预算生成路径'],
] as const

export function MultiAgentCallSequence({
  isRunning,
  events = [],
}: {
  isRunning: boolean
  events?: Array<AgentRunEvent>
}) {
  const latest = new Map(events.map((event) => [event.agent_name, event]))
  const hasRealEvents = events.length > 0
  const completed = events.some((event) => event.event_type === 'run_completed')

  return (
    <aside className="hidden min-h-0 overflow-y-auto border-l border-l-[#29496a] bg-[#102a46] text-slate-100 xl:flex xl:flex-col">
      <header className="border-b border-white/10 bg-[#0d243d] px-5 py-4">
        <div className="text-xs tracking-[0.16em] text-sky-200/70">AI ORCHESTRATION</div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <h2 className="font-semibold">多智能体真实事件</h2>
          <span className="border border-sky-300/30 px-2 py-1 text-xs text-sky-200">
            {hasRealEvents ? (completed ? '已完成' : '事件驱动') : isRunning ? '等待运行事件' : '待命'}
          </span>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-300/75">
          仅在收到服务端事件后更新，不使用定时器模拟步骤。
        </p>
      </header>
      <div className="flex-1 px-5 py-2">
        {stages.map(([agentName, name, description], index) => {
          const event = latest.get(agentName)
          const isActive = event?.status === 'running'
          const isCompleted = event?.status === 'completed'
          return (
            <section key={agentName} className="grid grid-cols-[36px_minmax(0,1fr)_64px] items-center border-b border-white/10 py-4">
              <span className="font-mono text-xs text-sky-200/55">{String(index + 1).padStart(2, '0')}</span>
              <div className="pr-3">
                <h3 className="text-sm font-medium">{name}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-300/70">{event?.summary ?? description}</p>
              </div>
              <div className="text-right text-xs">
                {isActive ? <span className="inline-flex items-center gap-1 text-sky-300"><Loader2Icon className="size-3.5 animate-spin" />执行中</span> : isCompleted ? <span className="inline-flex items-center gap-1 text-emerald-300"><CheckIcon className="size-3.5" />完成</span> : <span className="text-slate-400">待命</span>}
              </div>
            </section>
          )
        })}
      </div>
    </aside>
  )
}
