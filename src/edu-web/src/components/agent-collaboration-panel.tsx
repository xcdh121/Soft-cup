import {
  CheckCircle2Icon,
  ChevronRightIcon,
  CircleAlertIcon,
  Loader2Icon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export type CollaborationStep = {
  agentName: string
  status: string
  summary: string
  phase?: string
  eventType?: string
  skillId?: string
  skillDisplayName?: string
  toolCallId?: string
  toolName?: string
  toolDisplayName?: string
  evidenceCount?: number
  durationMs?: number | null
  fallbackUsed?: boolean
}

const agentLabels: Record<string, string> = {
  SupervisorAgent: '总控编排',
  ProfileAgent: '学习者画像',
  KTAgent: '知识状态评估',
  CollectiveInsightAgent: '群体学习洞察',
  DiagnosisAgent: '学习诊断',
  ResourceAgent: '资源规划',
  PlannerAgent: '学习路径规划',
}

export function AgentCollaborationPanel({
  steps,
  demoMode = false,
}: {
  steps: Array<CollaborationStep>
  demoMode?: boolean
}) {
  if (steps.length === 0) return null
  const running = steps.some((step) => step.status === 'running')
  const agents = Array.from(new Set(steps.map((step) => step.agentName)))
  return (
    <details
      className="group rounded-2xl border bg-background"
      open={demoMode || undefined}
    >
      <summary className="flex cursor-pointer list-none items-center gap-3 p-5">
        {running ? (
          <Loader2Icon className="size-4 animate-spin text-primary" />
        ) : (
          <CheckCircle2Icon className="size-4 text-emerald-600" />
        )}
        <div className="min-w-0 flex-1">
          <div className="font-medium">智能体协作详情</div>
          <div className="text-sm text-muted-foreground">
            {agents.length} 个智能体参与 · {running ? '正在运行' : '已完成'}
          </div>
        </div>
        <ChevronRightIcon className="size-4 transition-transform group-open:rotate-90" />
      </summary>
      <div className="space-y-3 border-t p-5">
        {agents.map((agentName) => {
          const agentSteps = steps.filter(
            (step) => step.agentName === agentName,
          )
          const latest = agentSteps.at(-1)!
          const skills = Array.from(
            new Map(
              agentSteps
                .filter((step) => step.eventType?.startsWith('skill_'))
                .map((step) => [step.skillId ?? step.skillDisplayName, step]),
            ).values(),
          )
          const tools = agentSteps.filter((step) =>
            step.eventType?.startsWith('tool_call_'),
          )
          return (
            <section key={agentName} className="rounded-xl border p-4">
              <div className="flex items-start gap-2">
                {latest.status === 'failed' ? (
                  <CircleAlertIcon className="mt-0.5 size-4 text-amber-600" />
                ) : latest.status === 'running' ? (
                  <Loader2Icon className="mt-0.5 size-4 animate-spin text-primary" />
                ) : (
                  <CheckCircle2Icon className="mt-0.5 size-4 text-emerald-600" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {agentLabels[agentName] ?? agentName}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {latest.summary}
                  </p>
                  {skills.map((skill) => (
                    <div
                      key={`${skill.skillId}-${skill.phase}`}
                      className="mt-2 flex flex-wrap gap-2"
                    >
                      <Badge variant="secondary">
                        能力：{skill.skillDisplayName ?? skill.skillId}
                      </Badge>
                      {skill.fallbackUsed && (
                        <Badge variant="outline">已使用保守回退</Badge>
                      )}
                    </div>
                  ))}
                  {tools.length > 0 && (
                    <div className="mt-3 space-y-2 border-l pl-3">
                      {tools.map((tool) => (
                        <div
                          key={
                            tool.toolCallId ??
                            `${tool.toolName}-${tool.summary}`
                          }
                          className="text-sm"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={cn(
                                'font-medium',
                                tool.status !== 'completed' && 'text-amber-700',
                              )}
                            >
                              {tool.toolDisplayName ?? tool.toolName}
                            </span>
                            {typeof tool.evidenceCount === 'number' && (
                              <span className="text-xs text-muted-foreground">
                                {tool.evidenceCount} 条证据
                              </span>
                            )}
                            {typeof tool.durationMs === 'number' && (
                              <span className="text-xs text-muted-foreground">
                                {tool.durationMs} ms
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {tool.summary}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          )
        })}
      </div>
    </details>
  )
}
