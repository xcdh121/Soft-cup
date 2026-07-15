import ELK from 'elkjs/lib/elk.bundled.js'
import { Position } from '@xyflow/react'
import type { Edge, Node } from '@xyflow/react'

const elk = new ELK()

const NODE_WIDTH = 224
const NODE_HEIGHT = 112

export async function layoutKnowledgeGraph(
  nodes: Array<Node>,
  edges: Array<Edge>,
) {
  const graph = await elk.layout({
    id: 'knowledge-graph',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '48',
      'elk.layered.spacing.nodeNodeBetweenLayers': '96',
      'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
      'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  })

  const positions = new Map(
    (graph.children ?? []).map((node) => [
      node.id,
      { x: node.x ?? 0, y: node.y ?? 0 },
    ]),
  )

  return {
    nodes: nodes.map((node) => ({
      ...node,
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    })),
    edges,
  }
}
