import type { AgentRun, AgentRunEvent } from '@/data-acess/agent-runs'

export type PlannerExecution = {
  mode: 'llm' | 'rule_fallback' | 'pending'
  modelName: string | null
  inputTokens: number
  outputTokens: number
}

const numberFrom = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0

export const getPlannerExecution = (
  run: AgentRun | null,
  events: Array<AgentRunEvent>,
): PlannerExecution => {
  const plannerEvents = events.filter(
    (event) => event.agent_name === 'PlannerAgent',
  )
  const completed = [...plannerEvents]
    .reverse()
    .find(
      (event) =>
        event.event_type === 'step_completed' ||
        (event.event_type === 'agent_step' &&
          event.payload.phase === 'completed'),
    )
  const fallbackEvent = plannerEvents.some(
    (event) => event.event_type === 'fallback_applied',
  )
  const reasonCodes = Array.isArray(completed?.payload.reason_codes)
    ? completed.payload.reason_codes.map(String)
    : []
  const plannerUsage = run?.usage?.agents?.find(
    (agent) => agent.agent_name === 'PlannerAgent',
  )
  const modelName =
    (typeof completed?.payload.model_name === 'string'
      ? completed.payload.model_name
      : null) ??
    plannerUsage?.model_name ??
    null
  const inputTokens =
    numberFrom(completed?.payload.input_tokens) ||
    plannerUsage?.input_tokens ||
    0
  const outputTokens =
    numberFrom(completed?.payload.output_tokens) ||
    plannerUsage?.output_tokens ||
    0
  const fallbackUsed =
    fallbackEvent ||
    completed?.payload.fallback_used === true ||
    reasonCodes.includes('rule') ||
    reasonCodes.includes('rule_fallback')
  const modelUsed =
    reasonCodes.includes('llm') ||
    Boolean(modelName) ||
    inputTokens + outputTokens > 0

  return {
    mode: fallbackUsed ? 'rule_fallback' : modelUsed ? 'llm' : 'pending',
    modelName,
    inputTokens,
    outputTokens,
  }
}
