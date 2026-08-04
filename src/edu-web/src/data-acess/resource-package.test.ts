import { describe, expect, it } from 'vitest'
import {
  applyResourcePackageStreamEvent,
  upsertAgentProgressStep,
} from './resource-package'

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

describe('applyResourcePackageStreamEvent', () => {
  it('hydrates a package opened from chat with its first durable snapshot', () => {
    const progress = applyResourcePackageStreamEvent(
      null,
      {
        event: 'package_snapshot',
        package_id: 'package-1',
        payload: {
          package: {
            id: 'package-1',
            status: 'generating',
            preferred_resource_types: ['lecture_note'],
            resources: [],
          },
        },
      },
      { projectId: 'project-1' },
    )

    expect(progress.packageId).toBe('package-1')
    expect(progress.status).toBe('generating')
    expect(progress.resourceStatuses).toEqual({ lecture_note: 'pending' })
    expect(progress.package?.id).toBe('package-1')
  })

  it('renders note content as soon as a resource delta arrives', () => {
    const progress = applyResourcePackageStreamEvent(
      null,
      {
        event: 'resource_delta',
        package_id: 'package-1',
        payload: {
          resource_id: 'resource-1',
          resource_type: 'lecture_note',
          title: 'Streaming note',
          content: '# First paragraph',
        },
      },
      { projectId: 'project-1', requestedTypes: ['lecture_note'] },
    )

    expect(progress.resources[0].content_text).toBe('# First paragraph')
    expect(progress.resourceStatuses.lecture_note).toBe('generating')
  })
})
