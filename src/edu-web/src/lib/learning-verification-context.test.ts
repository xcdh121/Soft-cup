// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest'
import {
  activateLearningVerification,
  consumeLearningVerification,
  readLearningVerification,
} from './learning-verification-context'

afterEach(() => sessionStorage.clear())

describe('learning verification context', () => {
  it('carries the recommendation and path into one matching quiz record', () => {
    activateLearningVerification({
      projectId: 'project-1',
      recommendationId: 'recommendation-1',
      learningPathId: 'path-1',
      learningPathStepId: 'step-1',
      knowledgePointId: 'kp-greedy',
      objective: '完成贪心算法验证题',
    })

    expect(readLearningVerification('project-1')).toMatchObject({
      recommendationId: 'recommendation-1',
      learningPathId: 'path-1',
      learningPathStepId: 'step-1',
      knowledgePointId: 'kp-greedy',
    })
    expect(consumeLearningVerification('project-1', 'kp-other')).toBeNull()
    expect(consumeLearningVerification('project-1', 'kp-greedy')).toMatchObject(
      { recommendationId: 'recommendation-1' },
    )
    expect(readLearningVerification('project-1')).toBeNull()
  })

  it('does not leak verification context into another project', () => {
    activateLearningVerification({
      projectId: 'project-1',
      recommendationId: 'recommendation-1',
      learningPathId: 'path-1',
      learningPathStepId: 'step-1',
      knowledgePointId: 'kp-greedy',
      objective: '验证',
    })

    expect(readLearningVerification('project-2')).toBeNull()
  })
})
