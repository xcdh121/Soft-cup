// @vitest-environment jsdom

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { filterKnowledgeGraph } from './filter-knowledge-graph'
import { KnowledgeGraphCanvas } from './knowledge-graph-canvas'
import type {
  KnowledgeGraph,
  KnowledgeStateEvent,
} from '@/data-acess/knowledge-graph'

const graph: KnowledgeGraph = {
  project_id: 'project-1',
  course_id: 'course-1',
  nodes: [
    {
      id: 'point-1',
      label: '二分查找',
      chapter_id: 'chapter-1',
      difficulty_level: 'intermediate',
      position: 1,
      tags: ['算法'],
      mastery_score: 49,
      mastery_probability: 0.49,
      p_correct_next: 0.54,
      confidence: 0.83,
      evidence_confidence: 0.83,
      trend: 'up',
      status: 'developing',
      algorithm: 'bkt',
      model_version: 'bkt-v1.0',
    },
  ],
  edges: [],
}

const events: Array<KnowledgeStateEvent> = Array.from(
  { length: 8 },
  (_, index) => ({
    id: `event-${index}`,
    event_type: 'practice',
    source_type: 'practice_record',
    source_id: `practice-${index}`,
    score_before: 40 + index,
    score_after: 41 + index,
    impact: 1,
    algorithm: 'expert_bkt',
    parameter_set_id: 'bkt-default',
    prior_mastery: 0.4,
    prior_after_forgetting: 0.39,
    posterior_after_observation: 0.48,
    posterior_after_learning: 0.52,
    p_correct_before: 0.4,
    p_correct_next: 0.5,
    observed_score: 1,
    event_weight: 1,
    effective_parameters: {
      learn_probability: 0.12,
      slip_probability: 0.1,
      guess_probability: 0.2,
    },
    reason_codes: ['correct_answer'],
    explanation_summary: `第 ${index + 1} 次状态更新`,
    model_version: 'bkt-v1.0',
    occurred_at: '2026-08-08T08:00:00Z',
  }),
)

afterEach(cleanup)

describe('KnowledgeGraphCanvas', () => {
  it('keeps long knowledge-point details inside one scrollable panel', () => {
    const { getByTestId } = render(
      <KnowledgeGraphCanvas
        activeStatuses={new Set()}
        events={events}
        graph={graph}
        selectedNodeId="point-1"
        onClearStatusFilters={vi.fn()}
        onSelect={vi.fn()}
        onStatusToggle={vi.fn()}
      />,
    )

    const panel = getByTestId('knowledge-point-detail-panel')
    expect(panel.className).toContain('h-full')
    expect(panel.className).toContain('w-full')
    expect(panel.className).toContain('overflow-y-auto')
    expect(panel.className).toContain('overscroll-contain')
    expect(panel.textContent).toContain('第 8 次状态更新')

    const panelViewport = panel.parentElement
    expect(panelViewport?.getAttribute('width')).toBe('480')
    expect(panelViewport?.getAttribute('height')).toBe('580')

    expect(() => fireEvent.wheel(panel, { deltaY: 120 })).not.toThrow()
  })

  it('turns every knowledge status into a controlled filter button', () => {
    const onStatusToggle = vi.fn()
    const onClearStatusFilters = vi.fn()
    const { getByRole, getByTestId } = render(
      <KnowledgeGraphCanvas
        activeStatuses={new Set(['developing'])}
        events={[]}
        graph={graph}
        selectedNodeId={null}
        onClearStatusFilters={onClearStatusFilters}
        onSelect={vi.fn()}
        onStatusToggle={onStatusToggle}
      />,
    )

    const developing = getByTestId('knowledge-status-filter-developing')
    expect(developing.getAttribute('aria-pressed')).toBe('true')
    expect(
      getByTestId('knowledge-status-filter-mastered').getAttribute(
        'aria-pressed',
      ),
    ).toBe('false')

    fireEvent.click(developing)
    expect(onStatusToggle).toHaveBeenCalledWith('developing')

    fireEvent.click(getByRole('button', { name: '全部' }))
    expect(onClearStatusFilters).toHaveBeenCalledOnce()
  })

  it('filters nodes and edges by the exact backend knowledge status', () => {
    const graphWithStatuses: KnowledgeGraph = {
      ...graph,
      nodes: [
        graph.nodes[0],
        { ...graph.nodes[0], id: 'point-2', status: 'mastered' },
      ],
      edges: [
        {
          id: 'edge-1',
          source: 'point-1',
          target: 'point-2',
          relation_type: 'prerequisite',
          strength: 1,
          description: null,
        },
      ],
    }

    const filtered = filterKnowledgeGraph(
      graphWithStatuses,
      '',
      false,
      new Set(['developing']),
    )

    expect(filtered.nodes.map((node) => node.id)).toEqual(['point-1'])
    expect(filtered.edges).toEqual([])
  })
})
