import { CheckIcon, Loader2Icon, MinusIcon } from 'lucide-react'
import type { ChatRuntimeEvent } from '@/data-acess/chat'

export function MultiAgentCallSequence({
  isRunning,
  events = [],
}: {
  isRunning: boolean
  events?: Array<ChatRuntimeEvent>
}) {
  const hasRealEvents = events.length > 0
  const completed =
    hasRealEvents && events.every((event) => event.status !== 'running')

  return (
    <aside className="hidden min-h-0 overflow-y-auto border-l border-l-[#29496a] bg-[#102a46] text-slate-100 xl:flex xl:flex-col">
      <header className="border-b border-white/10 bg-[#0d243d] px-5 py-4">
        <div className="text-xs tracking-[0.16em] text-sky-200/70">
          MULTI-AGENT ORCHESTRATION
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <h2 className="font-semibold">多智能体调用流程</h2>
          <span className="border border-sky-300/30 px-2 py-1 text-xs text-sky-200">
            {hasRealEvents
              ? completed
                ? '协同完成'
                : '协同执行中'
              : isRunning
                ? '等待智能体事件'
                : '待命'}
          </span>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-300/75">
          调度、学习上下文、意图路由、检索、工具与导师六个处理智能体按服务端 SSE
          真实事件更新；本轮不需要的步骤会明确标记为未调用。
        </p>
      </header>
      <div className="flex-1 px-5 py-2">
        {!hasRealEvents && (
          <div className="border-b border-white/10 py-5 text-sm text-slate-300/70">
            发送问题后，这里会展示本次请求的多智能体协同链路。
          </div>
        )}
        {events.map((event, index) => {
          const isActive = event.status === 'running'
          const isCompleted = event.status === 'completed'
          const isSkipped = event.status === 'skipped'
          return (
            <section
              key={event.id}
              className="grid grid-cols-[36px_minmax(0,1fr)_64px] items-center border-b border-white/10 py-4"
            >
              <span className="flex size-7 items-center justify-center rounded-full border border-sky-300/30 bg-sky-300/10 font-mono text-[11px] text-sky-200">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="pr-3">
                <h3 className="text-sm font-medium">{event.label}</h3>
                <p className="mt-1 text-[11px] text-sky-200/55">
                  {event.actor}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-300/70">
                  {event.summary}
                </p>
              </div>
              <div className="text-right text-xs">
                {isActive ? (
                  <span className="inline-flex items-center gap-1 text-sky-300">
                    <Loader2Icon className="size-3.5 animate-spin" />
                    执行中
                  </span>
                ) : isCompleted ? (
                  <span className="inline-flex items-center gap-1 text-emerald-300">
                    <CheckIcon className="size-3.5" />
                    完成
                  </span>
                ) : isSkipped ? (
                  <span className="inline-flex items-center gap-1 text-slate-400">
                    <MinusIcon className="size-3.5" />
                    未调用
                  </span>
                ) : (
                  <span className="text-rose-300">失败</span>
                )}
              </div>
            </section>
          )
        })}
      </div>
    </aside>
  )
}
