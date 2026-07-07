import { useEffect, useMemo, useState } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react'
import type { Edge, NodeMouseHandler } from '@xyflow/react'
import type {
  KnowledgeGraph,
  KnowledgeGraphNode,
} from '@/data-acess/knowledge-graph'
import { KnowledgeNode, type KnowledgeFlowNode } from './knowledge-node'
import { layoutKnowledgeGraph } from './layout-knowledge-graph'
import '@xyflow/react/dist/style.css'

const nodeTypes = { knowledge: KnowledgeNode }

function collectRelatedNodeIds(
  selectedId: string,
  edges: Array<Edge>,
): Set<string> {
  const related = new Set([selectedId])
  let changed = true
  while (changed) {
    changed = false
    edges.forEach((edge) => {
      if (related.has(edge.target) && !related.has(edge.source)) {
        related.add(edge.source)
        changed = true
      }
      if (related.has(edge.source) && !related.has(edge.target)) {
        related.add(edge.target)
        changed = true
      }
    })
  }
  return related
}

function KnowledgeGraphFlow({
  graph,
  onSelect,
}: {
  graph: KnowledgeGraph
  onSelect: (node: KnowledgeGraphNode | null) => void
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<KnowledgeFlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const { fitView } = useReactFlow()

  const rawElements = useMemo(() => {
    const graphNodes: Array<KnowledgeFlowNode> = graph.nodes.map((node) => ({
      id: node.id,
      type: 'knowledge',
      position: { x: 0, y: 0 },
      data: { ...node, isDimmed: false, isPath: false },
    }))
    const graphEdges: Array<Edge> = graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label:
        edge.relation_type === 'prerequisite' ? undefined : edge.relation_type,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { strokeWidth: Math.max(1.5, edge.strength * 2) },
      animated: false,
    }))
    return { graphNodes, graphEdges }
  }, [graph])

  useEffect(() => {
    let active = true
    layoutKnowledgeGraph(rawElements.graphNodes, rawElements.graphEdges).then(
      (layout) => {
        if (!active) return
        setNodes(layout.nodes as Array<KnowledgeFlowNode>)
        setEdges(layout.edges)
        requestAnimationFrame(() => fitView({ padding: 0.16, duration: 350 }))
      },
    )
    return () => {
      active = false
    }
  }, [fitView, rawElements, setEdges, setNodes])

  useEffect(() => {
    const related = selectedId
      ? collectRelatedNodeIds(selectedId, rawElements.graphEdges)
      : null
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        data: {
          ...node.data,
          isPath: Boolean(related?.has(node.id)),
          isDimmed: Boolean(related && !related.has(node.id)),
        },
      })),
    )
    setEdges((current) =>
      current.map((edge) => ({
        ...edge,
        animated: Boolean(
          related?.has(edge.source) && related.has(edge.target),
        ),
        style: {
          ...edge.style,
          opacity:
            related && !(related.has(edge.source) && related.has(edge.target))
              ? 0.15
              : 1,
        },
      })),
    )
  }, [rawElements.graphEdges, selectedId, setEdges, setNodes])

  const handleNodeClick: NodeMouseHandler<KnowledgeFlowNode> = (_, node) => {
    setSelectedId(node.id)
    onSelect(graph.nodes.find((item) => item.id === node.id) ?? null)
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      onPaneClick={() => {
        setSelectedId(null)
        onSelect(null)
      }}
      nodesDraggable={false}
      nodesConnectable={false}
      fitView
      minZoom={0.2}
      maxZoom={1.8}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={24} size={1} />
      <Controls showInteractive={false} />
      {graph.nodes.length > 15 && <MiniMap pannable zoomable />}
    </ReactFlow>
  )
}

export function KnowledgeGraphCanvas({
  graph,
  onSelect,
}: {
  graph: KnowledgeGraph
  onSelect: (node: KnowledgeGraphNode | null) => void
}) {
  return (
    <ReactFlowProvider>
      <KnowledgeGraphFlow graph={graph} onSelect={onSelect} />
    </ReactFlowProvider>
  )
}
