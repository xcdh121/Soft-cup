import { afterEach, describe, expect, it, vi } from 'vitest'
import { getResourceStats, splitRadarLabel } from './learning-evaluation-page'
import type { EvaluationResource } from '@/data-acess/learning-evaluation'

const programmingResource: EvaluationResource = {
  id: 'resource-1',
  type: 'programming_questions',
  name: '编程练习',
  createdAt: '2026-08-18T00:00:00Z',
  itemCount: 2,
  answeredCount: 0,
  wrongCount: 0,
  status: 'incomplete',
  questions: ['q1', 'q2'].map((id) => ({
    id,
    resourceId: 'resource-1',
    resourceName: '编程练习',
    type: 'programming_questions' as const,
    title: id,
    knowledgePoints: [],
    knowledgePointIds: [],
    attemptCount: 0,
    correctCount: 0,
    wrongCount: 0,
    completed: false,
    accuracy: null,
  })),
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('splitRadarLabel', () => {
  it('keeps every character while wrapping long knowledge-point labels', () => {
    const label = '时间与空间复杂度综合分析'
    const lines = splitRadarLabel(label, 6)

    expect(lines.length).toBeGreaterThan(1)
    expect(lines.join('')).toBe(label)
    expect(lines.every((line) => Array.from(line).length <= 6)).toBe(true)
  })
})

describe('getResourceStats for programming exercises', () => {
  it('uses code submission scores and completes after every question is run', () => {
    const getItem = vi.fn((key: string) => {
      if (key.startsWith('programming-submissions:')) {
        return JSON.stringify({
          q1: { score: 100 },
          q2: { score: 50 },
          staleQuestion: { score: 100 },
        })
      }
      if (key.startsWith('programming-grades:')) {
        return JSON.stringify({ q1: { score: 0 } })
      }
      return null
    })
    vi.stubGlobal('window', { localStorage: { getItem } })

    expect(getResourceStats('project-1', programmingResource)).toEqual({
      attemptCount: 2,
      accuracy: 75,
      completed: true,
    })
    expect(getItem).toHaveBeenCalledWith(
      'programming-submissions:project-1:resource-1',
    )
    expect(getItem).not.toHaveBeenCalledWith(
      'programming-grades:project-1:resource-1',
    )
  })

  it('stays incomplete until every question has a code submission', () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: () => JSON.stringify({ q1: { score: 80 } }),
      },
    })

    expect(getResourceStats('project-1', programmingResource)).toEqual({
      attemptCount: 1,
      accuracy: 80,
      completed: false,
    })
  })
})
