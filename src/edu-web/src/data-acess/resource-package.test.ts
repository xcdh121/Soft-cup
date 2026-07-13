import { describe, expect, it } from 'vitest'
import { upsertAgentProgressStep } from './resource-package'

describe('upsertAgentProgressStep', () => {
  it('replaces skill started with completed instead of duplicating it', () => {
    const started = {
      agentName: 'DiagnosisAgent',
      status: 'running',
      summary: 'started',
      eventType: 'skill_started',
      skillId: 'root_cause_diagnosis',
    }
    const completed = {
      ...started,
      status: 'completed',
      summary: 'completed',
      eventType: 'skill_completed',
      fallbackUsed: true,
    }

    const steps = upsertAgentProgressStep(
      upsertAgentProgressStep([], started),
      completed,
    )

    expect(steps).toEqual([completed])
  })

  it('replaces run lifecycle events so a completed run is not left running', () => {
    const started = {
      agentName: 'SupervisorAgent',
      status: 'running',
      summary: 'started',
      eventType: 'run_started',
    }
    const completed = {
      ...started,
      status: 'completed',
      summary: 'completed',
      eventType: 'run_completed',
    }

    const steps = upsertAgentProgressStep(
      upsertAgentProgressStep([], started),
      completed,
    )

    expect(steps).toEqual([completed])
  })
})
