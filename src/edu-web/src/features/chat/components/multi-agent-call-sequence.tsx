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
    <aside className="hidden min-h-0 overflow-y-auto border-l bg-background xl:flex xl:flex-col">
      <header className="border-b px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium tracking-[0.16em] text-muted-foreground">
              AI ORCHESTRATION
            </div>
            <h2 className="mt-1 text-base font-semibold">多智能体调用顺序</h2>
          </div>
          <span
            className={`border px-2 py-1 text-xs font-medium ${
              isRunning
                ? 'border-primary/40 bg-primary/5 text-primary'
                : hasCompleted
                  ? 'border-emerald-600/30 text-emerald-700'
                  : 'text-muted-foreground'
            }`}
          >
            {headerStatus}
          </span>
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
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
              className={`grid grid-cols-[36px_minmax(0,1fr)_56px] items-center border-b py-4 ${
                isActive ? 'border-l-2 border-l-primary bg-primary/[0.035]' : ''
              }`}
            >
              <span className="font-mono text-xs text-muted-foreground">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 pr-3">
                <h3 className="text-sm font-medium">{stage.name}</h3>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {stage.description}
                </p>
              </div>
              <div className="flex justify-end text-xs">
                {isActive ? (
                  <span className="flex items-center gap-1 text-primary">
                    <Loader2Icon className="size-3.5 animate-spin" />
                    执行中
                  </span>
                ) : isCompleted ? (
                  <span className="flex items-center gap-1 text-emerald-700">
                    <CheckIcon className="size-3.5" />
                    完成
                  </span>
                ) : (
                  <span className="text-muted-foreground">待命</span>
                )}
              </div>
            </section>
          )
        })}
      </div>
    </aside>
  )
}
