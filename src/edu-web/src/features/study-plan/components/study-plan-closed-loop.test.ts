// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import {
  getAdjustedOutcomeIds,
  getRecommendationResourceDestination,
  getRecommendationStage,
  groupInterventionOutcomes,
} from './study-plan-closed-loop'
import type {
  InterventionOutcome,
  RecommendationInteraction,
} from '@/data-acess/learning-closed-loop'

const interaction = (
  eventType: RecommendationInteraction['event_type'],
): RecommendationInteraction => ({
  id: `interaction-${eventType}`,
  recommendation_id: 'recommendation-1',
  event_type: eventType,
  resource_id: null,
  learning_session_id: null,
  progress: null,
  duration_ms: null,
  rating: null,
  reason_code: null,
  occurred_at: '2026-08-08T08:00:00Z',
  metadata: {},
})

describe('getRecommendationResourceDestination', () => {
  it('opens every generated recommendation on its real detail page', () => {
    expect(getRecommendationResourceDestination('quiz', 'quiz-1')).toBe('quiz')
    expect(getRecommendationResourceDestination('flashcards', 'cards-1')).toBe(
      'flashcards',
    )
    expect(getRecommendationResourceDestination('note', 'note-1')).toBe('note')
    expect(getRecommendationResourceDestination('mind_map', 'map-1')).toBe(
      'mind_map',
    )
  })

  it('uses actionable fallbacks only when there is no direct target', () => {
    expect(getRecommendationResourceDestination('practice', 'kp-1')).toBe(
      'practice',
    )
    expect(getRecommendationResourceDestination('note', null)).toBe(
      'resource_packages',
    )
  })
})

describe('getRecommendationStage', () => {
  it('uses the furthest real execution event instead of resource generation', () => {
    expect(getRecommendationStage([])).toBe('unseen')
    expect(getRecommendationStage([interaction('impression')])).toBe('seen')
    expect(
      getRecommendationStage([
        interaction('impression'),
        interaction('clicked'),
        interaction('started'),
      ]),
    ).toBe('started')
  })

  it('keeps completed ahead of ratings and earlier interactions', () => {
    expect(
      getRecommendationStage([
        interaction('started'),
        interaction('completed'),
        interaction('rated'),
      ]),
    ).toBe('completed')
  })

  it('treats skipped recommendations as terminal feedback', () => {
    expect(
      getRecommendationStage([
        interaction('impression'),
        interaction('skipped'),
      ]),
    ).toBe('skipped')
  })
})

const outcome = (
  id: string,
  recommendationId: string,
  evaluatedAt: string,
): InterventionOutcome => ({
  id,
  recommendation_id: recommendationId,
  knowledge_point_id: 'knowledge-point-1',
  baseline_state_event_id: `baseline-${id}`,
  verification_event_id: `verification-${id}`,
  mastery_before: 0.4,
  mastery_after: 0.6,
  mastery_gain: 0.2,
  verification_score: 1,
  target_mastery: 0.6,
  target_achieved: true,
  attribution_confidence: 0.8,
  evaluation_window_hours: 24,
  evaluated_at: evaluatedAt,
  explanation_id: null,
})

describe('groupInterventionOutcomes', () => {
  it('shows one latest result per recommendation and retains older results as history', () => {
    const groups = groupInterventionOutcomes([
      outcome('old-a', 'recommendation-a', '2026-08-08T08:00:00Z'),
      outcome('only-b', 'recommendation-b', '2026-08-08T10:00:00Z'),
      outcome('new-a', 'recommendation-a', '2026-08-08T12:00:00Z'),
    ])

    expect(groups).toHaveLength(2)
    expect(groups[0]).toMatchObject({
      recommendationId: 'recommendation-a',
      latest: { id: 'new-a' },
      history: [{ id: 'old-a' }],
    })
    expect(groups[1]).toMatchObject({
      recommendationId: 'recommendation-b',
      latest: { id: 'only-b' },
      history: [],
    })
  })

  it('does not mutate the API response order while sorting each history', () => {
    const older = outcome('older', 'recommendation-a', '2026-08-08T08:00:00Z')
    const newer = outcome('newer', 'recommendation-a', '2026-08-08T12:00:00Z')
    const outcomes = [older, newer]

    groupInterventionOutcomes(outcomes)

    expect(outcomes.map((item) => item.id)).toEqual(['older', 'newer'])
  })
})

describe('getAdjustedOutcomeIds', () => {
  it('combines aggregate adjustment ids with the legacy single trigger id', () => {
    const ids = getAdjustedOutcomeIds({
      raw_learning_path: {
        adjust_trigger_id: 'legacy-outcome',
        adjust_trigger_ids: ['aggregate-a', 'aggregate-b'],
      },
    } as never)

    expect([...ids]).toEqual(['aggregate-a', 'aggregate-b', 'legacy-outcome'])
  })
})
