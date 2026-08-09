import { describe, expect, it } from 'vitest'
import { convertMindMapToTree, normalizeMindMapData } from './mind-map-view'

describe('mind map data compatibility', () => {
  it('unwraps graph data embedded in a generated resource', () => {
    const mapData = normalizeMindMapData({
      target_id: 'mind-map-1',
      map_data: {
        nodes: [
          { id: 'root', data: { label: '数据结构' } },
          { id: 'child', label: '线性表' },
        ],
        edges: [{ source: 'root', target: 'child' }],
      },
    })

    expect(mapData.nodes.map((node) => node.data.label)).toEqual([
      '数据结构',
      '线性表',
    ])
    expect(mapData.edges).toHaveLength(1)
  })

  it('normalizes persisted and legacy node labels', () => {
    const mapData = normalizeMindMapData({
      nodes: [
        { id: 'root', data: { label: '算法基础', detail: '核心知识' } },
        { id: 'child', label: '时间复杂度' },
      ],
      edges: [
        { id: 'valid', source: 'root', target: 'child' },
        { id: 'invalid', source: 'root', target: 'missing' },
      ],
    })

    expect(mapData.nodes.map((node) => node.data.label)).toEqual([
      '算法基础',
      '时间复杂度',
    ])
    expect(mapData.nodes[0].data.content).toBe('核心知识')
    expect(mapData.edges).toHaveLength(1)
  })

  it('renders cyclic AI relationships as a finite tree', () => {
    const mapData = normalizeMindMapData({
      nodes: [
        { id: 'root', data: { label: '图论' } },
        { id: 'child', data: { label: '遍历' } },
      ],
      edges: [
        { source: 'root', target: 'child' },
        { source: 'child', target: 'root' },
      ],
    })

    const tree = convertMindMapToTree(mapData.nodes, mapData.edges)

    expect(tree?.label).toBe('图论')
    expect(tree?.children?.[0].label).toBe('遍历')
    expect(tree?.children?.[0].children).toEqual([])
  })
})
