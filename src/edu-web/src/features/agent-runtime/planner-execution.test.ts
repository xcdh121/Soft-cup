import { describe, expect, it } from 'vitest'
import { getPlannerExecution } from './planner-execution'
import type { AgentRun, AgentRunEvent } from '@/data-acess/agent-runs'

const event = (
  eventType: string,
  payload: Record<string, unknown>,
): AgentRunEvent => ({
  event_type: eventType,
  run_id: 'run-1',
  agent_name: 'PlannerAgent',
  status: 'completed',
  summary: 'done',
  timestamp: '2026-08-14T08:00:00Z',
  payload,
  sequence: 1,
})

describe('getPlannerExecution', () => {
  it('reads model generation details from the completed Planner event', () => {
    const execution = getPlannerExecution(null, [
      event('step_completed', {
        phase: 'completed',
        reason_codes: ['learning_path_generated', 'llm'],
        fallback_used: false,
        model_name: 'deepseek-v4-pro',
        input_tokens: 120,
        output_tokens: 45,
      }),
    ])

    expect(execution).toEqual({
      mode: 'llm',
      modelName: 'deepseek-v4-pro',
      inputTokens: 120,
      outputTokens: 45,
    })
  })

  it('prefers the rule fallback state even when a model was attempted', () => {
    const execution = getPlannerExecution(null, [
      event('fallback_applied', {
        fallback_reason: 'planner_rule_fallback',
      }),
      event('step_completed', {
        phase: 'completed',
        reason_codes: ['learning_path_generated', 'rule_fallback'],
        fallback_used: true,
        model_name: 'deepseek-v4-pro',
      }),
    ])

    expect(execution.mode).toBe('rule_fallback')
    expect(execution.modelName).toBe('deepseek-v4-pro')
  })

  it('recovers usage from a persisted completed run', () => {
    const run = {
      usage: {
        agents: [
          {
            agent_name: 'PlannerAgent',
            model_name: 'deepseek-v4-pro',
            input_tokens: 4520,
            output_tokens: 2409,
          },
        ],
      },
    } as AgentRun

    expect(getPlannerExecution(run, [])).toMatchObject({
      mode: 'llm',
      inputTokens: 4520,
      outputTokens: 2409,
    })
  })
})
