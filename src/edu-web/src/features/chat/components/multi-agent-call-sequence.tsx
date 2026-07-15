import { CheckIcon, Loader2Icon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type AgentStage = {
  name: string
  description: string
}

const agentStages: Array<AgentStage> = [
  {
    name: '总控编排',
    description: '理解问题、拆解任务并确定协作链路',
  },
  {
    name: '学习者画像',
    description: '读取学习目标、偏好与当前学习进度',
  },
  {
    name: '知识状态评估',
    description: '结合练习记录评估知识点掌握情况',
  },
  {
    name: '学习诊断',
    description: '定位薄弱环节与问题背后的知识缺口',
  },
  {
    name: '资源规划',
    description: '检索项目资料并匹配学习资源',
  },
  {
    name: '学习路径规划',
    description: '汇总结论并生成回答与后续建议',
  },
]

export function MultiAgentCallSequence({ isRunning }: { isRunning: boolean }) {
  const wasRunningRef = useRef(false)
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [completedIndex, setCompletedIndex] = useState(-1)
  const [hasCompleted, setHasCompleted] = useState(false)

  useEffect(() => {
    let progressTimer: number | undefined

    if (isRunning) {
      if (!wasRunningRef.current) {
        setActiveIndex(0)
        setCompletedIndex(-1)
        setHasCompleted(false)
      }

      progressTimer = window.setInterval(() => {
        setActiveIndex((current) => {
          if (current === null || current >= agentStages.length - 1) {
            return current
          }
          setCompletedIndex(current)
          return current + 1
        })
      }, 1100)
    } else if (wasRunningRef.current) {
      setActiveIndex(null)
      setCompletedIndex(agentStages.length - 1)
      setHasCompleted(true)
    }

    wasRunningRef.current = isRunning
    return () => {
      if (progressTimer) window.clearInterval(progressTimer)
    }
  }, [isRunning])

  const headerStatus = isRunning
    ? '调用中'
    : hasCompleted
      ? '本次调用已完成'
      : '等待对话'

  return (
    <aside className="hidden min-h-0 overflow-y-auto border-l border-l-[#29496a] bg-[#102a46] text-slate-100 shadow-[-4px_0_18px_rgba(15,42,70,0.08)] xl:flex xl:flex-col">
      <header className="border-b border-white/10 bg-[#0d243d] px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium tracking-[0.16em] text-sky-200/70">
              AI ORCHESTRATION
            </div>
            <h2 className="mt-1 text-base font-semibold">多智能体调用顺序</h2>
          </div>
          <span
            className={`border px-2 py-1 text-xs font-medium ${
              isRunning
                ? 'border-sky-300/30 bg-sky-300/10 text-sky-200'
                : hasCompleted
                  ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-300'
                  : 'border-orange-300/30 bg-orange-400/10 text-orange-300'
            }`}
          >
            {headerStatus}
          </span>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-300/75">
          发送问题后，系统将按顺序推进本次协作流程。
        </p>
      </header>

      <div className="flex-1 px-5 py-2">
        {agentStages.map((stage, index) => {
          const isActive = activeIndex === index
          const isCompleted = completedIndex >= index

          return (
            <section
              key={stage.name}
              className={`grid grid-cols-[36px_minmax(0,1fr)_56px] items-center border-b border-white/10 py-4 ${
                isActive ? 'border-l-2 border-l-sky-300 bg-sky-300/[0.08]' : ''
              }`}
            >
              <span className="font-mono text-xs text-sky-200/55">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 pr-3">
                <h3 className="text-sm font-medium">{stage.name}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-300/70">
                  {stage.description}
                </p>
              </div>
              <div className="flex justify-end text-xs">
                {isActive ? (
                  <span className="flex items-center gap-1 text-sky-300">
                    <Loader2Icon className="size-3.5 animate-spin" />
                    执行中
                  </span>
                ) : isCompleted ? (
                  <span className="flex items-center gap-1 text-emerald-300">
                    <CheckIcon className="size-3.5" />
                    完成
                  </span>
                ) : (
                  <span className="text-orange-300">待命</span>
                )}
              </div>
            </section>
          )
        })}
      </div>
    </aside>
  )
}
