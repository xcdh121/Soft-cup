// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MindMapView } from './mind-map-view'

describe('MindMapView rendering', () => {
  it('renders a graph embedded in a generated-resource payload', () => {
    render(
      <div style={{ width: 800, height: 500 }}>
        <MindMapView
          mapData={{
            target_id: 'mind-map-1',
            map_data: {
              nodes: [
                { id: 'root', data: { label: '数据结构' } },
                { id: 'child', label: '线性表' },
              ],
              edges: [{ source: 'root', target: 'child' }],
            },
          }}
        />
      </div>,
    )

    expect(screen.getByText('数据结构')).toBeTruthy()
    expect(screen.getByText('线性表')).toBeTruthy()
  })
})
