import { useEffect, useMemo, useRef, useState } from 'react'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from 'd3-force'
import type { SimulationLinkDatum, SimulationNodeDatum } from 'd3-force'
import { Maximize2, RotateCcw } from 'lucide-react'
import type {
  KnowledgeGraph,
  KnowledgeGraphNode,
} from '@/data-acess/knowledge-graph'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Point = { x: number; y: number }
type Viewport = { zoom: number; pan: Point }
type DragState =
  | {
      type: 'pan'
      pointerId: number
      startPoint: Point
      startPan: Point
      moved: boolean
    }
  | {
      type: 'node'
      pointerId: number
      nodeId: string
      offset: Point
      moved: boolean
    }
type LayoutNode = SimulationNodeDatum & {
  id: string
  degree: number
  source: KnowledgeGraphNode
}
type LayoutLink = SimulationLinkDatum<LayoutNode> & {
  id: string
  source: string | LayoutNode
  target: string | LayoutNode
  strength: number
}

const statusLabel: Partial<Record<string, string>> = {
  not_started: '未开始',
  learning: '学习中',
  mastered: '已掌握',
}

const trendLabel: Partial<Record<string, string>> = {
  up: '上升',
  stable: '稳定',
  down: '下降',
}

const difficultyLabel: Partial<Record<string, string>> = {
  beginner: '入门',
  intermediate: '进阶',
  advanced: '高级',
}

function getMasteryColor(node: KnowledgeGraphNode) {
  if (node.status === 'not_started') return '#5483b3'
  if (node.mastery_score < 40) return '#7da0ca'
  if (node.mastery_score < 80) return '#c1e8ff'
  return '#052659'
}

function getNodeSize(node: KnowledgeGraphNode) {
  return 6 + Math.min(8, Math.max(0, node.mastery_score) / 14)
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function buildPositions(graph: KnowledgeGraph, seed: number) {
  const degree = new Map(graph.nodes.map((node) => [node.id, 0]))
  graph.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1)
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1)
  })

  const sortedNodes = [...graph.nodes].sort((a, b) => {
    const degreeDiff = (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)
    if (degreeDiff !== 0) return degreeDiff
    return a.position - b.position
  })
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))
  const graphNodeIds = new Set(graph.nodes.map((node) => node.id))
  const layoutNodes: Array<LayoutNode> = sortedNodes.map((node, index) => {
    const radius = index === 0 ? 0 : 90 + Math.sqrt(index) * 72
    const angle = index * goldenAngle + seed * 0.72
    const jitter = ((node.position % 11) - 5) * 8
    return {
      id: node.id,
      degree: degree.get(node.id) ?? 0,
      source: node,
      x: Math.cos(angle) * (radius + jitter),
      y: Math.sin(angle) * (radius - jitter),
    }
  })
  const links: Array<LayoutLink> = graph.edges
    .filter(
      (edge) => graphNodeIds.has(edge.source) && graphNodeIds.has(edge.target),
    )
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      strength: edge.strength,
    }))

  const simulation = forceSimulation(layoutNodes)
    .force(
      'link',
      forceLink<LayoutNode, LayoutLink>(links)
        .id((node) => node.id)
        .distance((link) => 112 - Math.min(42, link.strength * 38))
        .strength((link) => 0.18 + Math.min(0.5, link.strength * 0.36)),
    )
    .force(
      'charge',
      forceManyBody<LayoutNode>().strength(
        (node) => -190 - Math.min(280, node.degree * 42),
      ),
    )
    .force(
      'collide',
      forceCollide<LayoutNode>()
        .radius((node) => getNodeSize(node.source) + 46)
        .strength(0.86),
    )
    .force('x', forceX<LayoutNode>(0).strength(0.035))
    .force('y', forceY<LayoutNode>(0).strength(0.035))
    .force('center', forceCenter(0, 0))
    .stop()

  const tickCount = Math.min(420, 180 + graph.nodes.length * 5)
  for (let tick = 0; tick < tickCount; tick += 1) {
    simulation.tick()
  }
  simulation.stop()

  const positions = new Map<string, Point>()
  layoutNodes.forEach((node) => {
    positions.set(node.id, { x: node.x ?? 0, y: node.y ?? 0 })
  })

  return positions
}

function buildViewBox(positions: Map<string, Point>) {
  const points = [...positions.values()]
  if (points.length === 0) return '-500 -320 1000 640'
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const padding = 220
  return [
    minX - padding,
    minY - padding,
    Math.max(720, maxX - minX + padding * 2),
    Math.max(480, maxY - minY + padding * 2),
  ].join(' ')
}

function parseViewBox(viewBox: string) {
  const [x, y, width, height] = viewBox.split(' ').map((value) => Number(value))
  return { x, y, width, height }
}

function collectRelatedNodeIds(
  selectedId: string,
  edges: KnowledgeGraph['edges'],
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

function getConnectedNodes(
  graph: KnowledgeGraph,
  selectedNode: KnowledgeGraphNode | null,
) {
  if (!selectedNode) return { predecessors: [], successors: [] }
  const predecessors = graph.edges
    .filter((edge) => edge.target === selectedNode.id)
    .map((edge) => graph.nodes.find((node) => node.id === edge.source))
    .filter((node): node is KnowledgeGraphNode => Boolean(node))
  const successors = graph.edges
    .filter((edge) => edge.source === selectedNode.id)
    .map((edge) => graph.nodes.find((node) => node.id === edge.target))
    .filter((node): node is KnowledgeGraphNode => Boolean(node))
  return { predecessors, successors }
}

export function KnowledgeGraphCanvas({
  graph,
  selectedNodeId,
  onSelect,
}: {
  graph: KnowledgeGraph
  selectedNodeId: string | null
  onSelect: (node: KnowledgeGraphNode | null) => void
}) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const dragStateRef = useRef<DragState | null>(null)
  const [layoutSeed, setLayoutSeed] = useState(0)
  const [viewport, setViewport] = useState<Viewport>({
    zoom: 1,
    pan: { x: 0, y: 0 },
  })
  const basePositions = useMemo(
    () => buildPositions(graph, layoutSeed),
    [graph, layoutSeed],
  )
  const [positions, setPositions] = useState(basePositions)

  useEffect(() => {
    setPositions(new Map(basePositions))
    setViewport({ zoom: 1, pan: { x: 0, y: 0 } })
  }, [basePositions])

  const relatedIds = useMemo(
    () =>
      selectedNodeId
        ? collectRelatedNodeIds(selectedNodeId, graph.edges)
        : null,
    [graph.edges, selectedNodeId],
  )
  const viewBox = useMemo(() => buildViewBox(positions), [positions])
  const viewBoxRect = useMemo(() => parseViewBox(viewBox), [viewBox])
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  )
  const selectedPoint = selectedNode ? positions.get(selectedNode.id) : null
  const { predecessors, successors } = useMemo(
    () => getConnectedNodes(graph, selectedNode),
    [graph, selectedNode],
  )

  const clientToSvgPoint = (clientX: number, clientY: number): Point => {
    const svg = svgRef.current
    const matrix = svg?.getScreenCTM()
    if (!matrix) return { x: 0, y: 0 }
    const point = new DOMPoint(clientX, clientY).matrixTransform(
      matrix.inverse(),
    )
    return { x: point.x, y: point.y }
  }

  const clientToGraphPoint = (clientX: number, clientY: number): Point => {
    const point = clientToSvgPoint(clientX, clientY)
    return {
      x: (point.x - viewport.pan.x) / viewport.zoom,
      y: (point.y - viewport.pan.y) / viewport.zoom,
    }
  }

  const handleWheel = (event: React.WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    const svgPoint = clientToSvgPoint(event.clientX, event.clientY)
    const graphPoint = {
      x: (svgPoint.x - viewport.pan.x) / viewport.zoom,
      y: (svgPoint.y - viewport.pan.y) / viewport.zoom,
    }
    const nextZoom = clamp(
      viewport.zoom * (event.deltaY > 0 ? 0.88 : 1.14),
      0.35,
      3.2,
    )
    setViewport({
      zoom: nextZoom,
      pan: {
        x: svgPoint.x - graphPoint.x * nextZoom,
        y: svgPoint.y - graphPoint.y * nextZoom,
      },
    })
  }

  const handleCanvasPointerDown = (
    event: React.PointerEvent<SVGRectElement>,
  ) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    dragStateRef.current = {
      type: 'pan',
      pointerId: event.pointerId,
      startPoint: clientToSvgPoint(event.clientX, event.clientY),
      startPan: viewport.pan,
      moved: false,
    }
  }

  const handleNodePointerDown = (
    event: React.PointerEvent<SVGGElement>,
    node: KnowledgeGraphNode,
  ) => {
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = positions.get(node.id)
    if (!point) return
    const graphPoint = clientToGraphPoint(event.clientX, event.clientY)
    dragStateRef.current = {
      type: 'node',
      pointerId: event.pointerId,
      nodeId: node.id,
      offset: {
        x: graphPoint.x - point.x,
        y: graphPoint.y - point.y,
      },
      moved: false,
    }
  }

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const dragState = dragStateRef.current
    if (!dragState || dragState.pointerId !== event.pointerId) return

    if (dragState.type === 'pan') {
      const point = clientToSvgPoint(event.clientX, event.clientY)
      const nextPan = {
        x: dragState.startPan.x + point.x - dragState.startPoint.x,
        y: dragState.startPan.y + point.y - dragState.startPoint.y,
      }
      const moved =
        Math.abs(nextPan.x - dragState.startPan.x) > 2 ||
        Math.abs(nextPan.y - dragState.startPan.y) > 2
      dragStateRef.current = { ...dragState, moved: dragState.moved || moved }
      setViewport((current) => ({ ...current, pan: nextPan }))
      return
    }

    const graphPoint = clientToGraphPoint(event.clientX, event.clientY)
    const nextPoint = {
      x: graphPoint.x - dragState.offset.x,
      y: graphPoint.y - dragState.offset.y,
    }
    const previousPoint = positions.get(dragState.nodeId)
    const moved = previousPoint
      ? Math.hypot(
          nextPoint.x - previousPoint.x,
          nextPoint.y - previousPoint.y,
        ) > 1.5
      : false
    dragStateRef.current = { ...dragState, moved: dragState.moved || moved }
    setPositions((current) => {
      const next = new Map(current)
      next.set(dragState.nodeId, nextPoint)
      return next
    })
  }

  const handlePointerUp = (event: React.PointerEvent<SVGSVGElement>) => {
    const dragState = dragStateRef.current
    if (!dragState || dragState.pointerId !== event.pointerId) return
    dragStateRef.current = null
    if (dragState.type === 'pan') {
      if (!dragState.moved) onSelect(null)
      return
    }
    const node = graph.nodes.find((item) => item.id === dragState.nodeId)
    if (node) onSelect(node)
  }

  const resetView = () => {
    setViewport({ zoom: 1, pan: { x: 0, y: 0 } })
  }

  return (
    <div className="relative h-full min-h-[620px] overflow-hidden bg-[#021024]">
      <div
        className={cn(
          'pointer-events-none absolute inset-0 opacity-80',
          'bg-[radial-gradient(circle_at_20%_20%,rgba(84,131,179,0.25),transparent_25%),radial-gradient(circle_at_78%_28%,rgba(125,160,202,0.16),transparent_28%),linear-gradient(90deg,rgba(193,232,255,0.035)_1px,transparent_1px),linear-gradient(rgba(193,232,255,0.035)_1px,transparent_1px)] bg-[length:auto,auto,56px_56px,56px_56px]',
        )}
      />

      <svg
        ref={svgRef}
        aria-label="知识图谱"
        className="absolute inset-0 h-full w-full touch-none"
        role="img"
        viewBox={viewBox}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
      >
        <defs>
          <filter id="nodeGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker
            id="graphArrow"
            markerHeight="8"
            markerWidth="8"
            orient="auto"
            refX="7"
            refY="4"
          >
            <path d="M0,0 L8,4 L0,8 Z" fill="#5483b3" />
          </marker>
          <marker
            id="graphArrowActive"
            markerHeight="8"
            markerWidth="8"
            orient="auto"
            refX="7"
            refY="4"
          >
            <path d="M0,0 L8,4 L0,8 Z" fill="#c1e8ff" />
          </marker>
        </defs>

        <rect
          className="cursor-grab active:cursor-grabbing"
          fill="transparent"
          height={viewBoxRect.height}
          width={viewBoxRect.width}
          x={viewBoxRect.x}
          y={viewBoxRect.y}
          onPointerDown={handleCanvasPointerDown}
        />

        <g
          transform={`translate(${viewport.pan.x} ${viewport.pan.y}) scale(${viewport.zoom})`}
        >
          {graph.edges.map((edge) => {
            const source = positions.get(edge.source)
            const target = positions.get(edge.target)
            if (!source || !target) return null
            const isRelated =
              relatedIds?.has(edge.source) && relatedIds.has(edge.target)
            const isDimmed = Boolean(relatedIds && !isRelated)
            return (
              <line
                key={edge.id}
                markerEnd={`url(#${isRelated ? 'graphArrowActive' : 'graphArrow'})`}
                opacity={isDimmed ? 0.08 : isRelated ? 0.78 : 0.36}
                stroke={isRelated ? '#c1e8ff' : '#5483b3'}
                strokeLinecap="round"
                strokeWidth={Math.max(0.8, edge.strength * 1.8)}
                x1={source.x}
                x2={target.x}
                y1={source.y}
                y2={target.y}
              />
            )
          })}

          {graph.nodes.map((node) => {
            const point = positions.get(node.id)
            if (!point) return null
            const color = getMasteryColor(node)
            const isSelected = selectedNodeId === node.id
            const isRelated = Boolean(relatedIds?.has(node.id))
            const isDimmed = Boolean(relatedIds && !isRelated)
            const radius = getNodeSize(node)

            return (
              <g
                key={node.id}
                className="cursor-move"
                filter={isDimmed ? undefined : 'url(#nodeGlow)'}
                opacity={isDimmed ? 0.18 : 1}
                onPointerDown={(event) => handleNodePointerDown(event, node)}
              >
                <rect
                  fill={color}
                  height={radius * 1.55}
                  rx="2"
                  stroke={isSelected ? '#ffffff' : '#c1e8ff'}
                  strokeOpacity={isSelected ? 1 : 0.55}
                  strokeWidth={isSelected ? 2.5 : 1.1}
                  width={radius * 1.55}
                  x={point.x - radius * 0.775}
                  y={point.y - radius * 0.775}
                />
                <circle
                  cx={point.x}
                  cy={point.y}
                  fill="transparent"
                  r={Math.max(18, radius + 10)}
                />
                <text
                  dominantBaseline="middle"
                  fill={isSelected || isRelated ? '#ffffff' : '#c1e8ff'}
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
                  fontSize="13"
                  fontWeight={isSelected ? 700 : 600}
                  pointerEvents="none"
                  x={point.x + radius + 8}
                  y={point.y}
                >
                  {node.label}
                </text>
              </g>
            )
          })}
        </g>

        {selectedNode && selectedPoint && (
          <foreignObject
            height="230"
            width="300"
            x={selectedPoint.x * viewport.zoom + viewport.pan.x + 24}
            y={selectedPoint.y * viewport.zoom + viewport.pan.y - 18}
          >
            <div className="pointer-events-auto w-[292px] rounded-md border border-[#7DA0CA]/40 bg-[#052659]/95 p-4 font-sans text-xs text-[#C1E8FF] shadow-2xl shadow-[#021024]/50 backdrop-blur">
              <div className="mb-2 flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-white">
                    {selectedNode.label}
                  </div>
                  <div className="mt-1 text-[11px] text-[#7DA0CA]">
                    {difficultyLabel[selectedNode.difficulty_level] ??
                      selectedNode.difficulty_level}{' '}
                    / {statusLabel[selectedNode.status] ?? selectedNode.status}
                  </div>
                </div>
                <button
                  type="button"
                  className="rounded border border-[#7DA0CA]/40 px-1.5 text-[#C1E8FF] transition-colors hover:bg-[#021024] hover:text-white"
                  onClick={() => onSelect(null)}
                >
                  x
                </button>
              </div>

              <div className="mb-2">
                <div className="mb-1 flex justify-between text-[11px] text-[#7DA0CA]">
                  <span>掌握度</span>
                  <span>{Math.round(selectedNode.mastery_score)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-[#C1E8FF]"
                    style={{
                      width: `${clamp(selectedNode.mastery_score, 0, 100)}%`,
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div className="rounded border border-white/10 bg-white/[0.04] p-2">
                  <div className="text-slate-500">置信度</div>
                  <div>{Math.round(selectedNode.confidence * 100)}%</div>
                </div>
                <div className="rounded border border-white/10 bg-white/[0.04] p-2">
                  <div className="text-slate-500">趋势</div>
                  <div>
                    {trendLabel[selectedNode.trend] ?? selectedNode.trend}
                  </div>
                </div>
                <div className="rounded border border-white/10 bg-white/[0.04] p-2">
                  <div className="text-slate-500">关系</div>
                  <div>{predecessors.length + successors.length}</div>
                </div>
              </div>

              <div className="mt-3 space-y-1.5 text-[11px]">
                <div className="truncate text-[#7DA0CA]">
                  前置：
                  {predecessors.map((node) => node.label).join('、') || '无'}
                </div>
                <div className="truncate text-[#7DA0CA]">
                  后续：
                  {successors.map((node) => node.label).join('、') || '无'}
                </div>
              </div>
            </div>
          </foreignObject>
        )}
      </svg>

      <div className="absolute left-4 top-4 flex flex-wrap gap-2 text-[11px] font-medium text-[#C1E8FF]">
        <span className="rounded-full border border-[#5483B3]/50 bg-[#052659]/60 px-2.5 py-1 backdrop-blur">
          未开始
        </span>
        <span className="rounded-full border border-[#7DA0CA]/50 bg-[#7DA0CA]/15 px-2.5 py-1 text-[#C1E8FF] backdrop-blur">
          薄弱
        </span>
        <span className="rounded-full border border-[#C1E8FF]/50 bg-[#5483B3]/20 px-2.5 py-1 text-[#C1E8FF] backdrop-blur">
          学习中
        </span>
        <span className="rounded-full border border-white/40 bg-[#C1E8FF]/20 px-2.5 py-1 text-white backdrop-blur">
          已掌握
        </span>
      </div>

      <div className="absolute right-4 top-4 flex gap-2">
        <Button
          type="button"
          size="icon"
          variant="secondary"
          className="border border-[#7DA0CA]/40 bg-[#052659]/80 text-white hover:bg-[#021024]"
          title="重新模拟布局"
          onClick={() => {
            onSelect(null)
            setLayoutSeed((seed) => seed + 1)
          }}
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          size="icon"
          variant="secondary"
          className="border border-[#7DA0CA]/40 bg-[#052659]/80 text-white hover:bg-[#021024]"
          title="恢复视图"
          onClick={resetView}
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>

      <div className="absolute bottom-4 left-4 rounded-full border border-[#7DA0CA]/40 bg-[#052659]/70 px-3 py-1 text-xs text-[#C1E8FF] backdrop-blur">
        D3 force / 滚轮缩放 / 拖动画布与节点 / {graph.nodes.length} 个知识点 /{' '}
        {graph.edges.length} 条关系
      </div>
    </div>
  )
}
