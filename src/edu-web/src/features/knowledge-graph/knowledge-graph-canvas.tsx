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
import { Maximize2, RotateCcw } from 'lucide-react'
import type { SimulationLinkDatum, SimulationNodeDatum } from 'd3-force'
import type {
  KnowledgeGraph,
  KnowledgeGraphNode,
  KnowledgeStateEvent,
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

const DETAIL_PANEL_WIDTH = 480
const DETAIL_PANEL_HEIGHT = 580

export const KNOWLEDGE_STATUS_OPTIONS = [
  {
    value: 'not_started',
    label: '未开始',
    color: '#5483b3',
    className: 'border-[#5483B3]/60 bg-[#052659]/70',
  },
  {
    value: 'insufficient_evidence',
    label: '证据不足',
    color: '#8fa9bf',
    className: 'border-[#8FA9BF]/60 bg-[#8FA9BF]/15',
  },
  {
    value: 'weak',
    label: '薄弱',
    color: '#7da0ca',
    className: 'border-[#7DA0CA]/60 bg-[#7DA0CA]/15',
  },
  {
    value: 'learning',
    label: '学习中',
    color: '#c1e8ff',
    className: 'border-[#C1E8FF]/60 bg-[#C1E8FF]/15',
  },
  {
    value: 'developing',
    label: '发展中',
    color: '#76b5d8',
    className: 'border-[#76B5D8]/60 bg-[#76B5D8]/15',
  },
  {
    value: 'mastered',
    label: '已掌握',
    color: '#ffffff',
    className: 'border-white/60 bg-white/15',
  },
  {
    value: 'at_risk',
    label: '待复核',
    color: '#f3b66f',
    className: 'border-[#F3B66F]/60 bg-[#F3B66F]/15 text-[#FFE0B7]',
  },
] as const

const statusLabel: Partial<Record<string, string>> = {
  not_started: '未开始',
  learning: '学习中',
  insufficient_evidence: '证据不足',
  weak: '薄弱',
  developing: '发展中',
  mastered: '已掌握',
  at_risk: '待复核',
}

const trendLabel: Partial<Record<string, string>> = {
  up: '上升',
  stable: '稳定',
  down: '下降',
  insufficient_evidence: '证据不足',
}

const difficultyLabel: Partial<Record<string, string>> = {
  beginner: '入门',
  intermediate: '进阶',
  advanced: '高级',
}

function getMasteryColor(node: KnowledgeGraphNode) {
  const statusOption = KNOWLEDGE_STATUS_OPTIONS.find(
    (option) => option.value === node.status,
  )
  if (statusOption) return statusOption.color
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
    Math.max(640, maxY - minY + padding * 2),
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
  events,
  activeStatuses,
  onSelect,
  onStatusToggle,
  onClearStatusFilters,
}: {
  graph: KnowledgeGraph
  selectedNodeId: string | null
  events: Array<KnowledgeStateEvent>
  activeStatuses: ReadonlySet<string>
  onSelect: (node: KnowledgeGraphNode | null) => void
  onStatusToggle: (status: string) => void
  onClearStatusFilters: () => void
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
  const selectedViewportPoint = selectedPoint
    ? {
        x: selectedPoint.x * viewport.zoom + viewport.pan.x,
        y: selectedPoint.y * viewport.zoom + viewport.pan.y,
      }
    : null
  const detailPanelX = selectedViewportPoint
    ? (() => {
        const panelGap = 32
        const panelMargin = 16
        const minX = viewBoxRect.x + panelMargin
        const maxX =
          viewBoxRect.x + viewBoxRect.width - DETAIL_PANEL_WIDTH - panelMargin
        const rightX = selectedViewportPoint.x + panelGap
        const leftX = selectedViewportPoint.x - DETAIL_PANEL_WIDTH - panelGap
        const fitsRight = rightX <= maxX
        const fitsLeft = leftX >= minX
        const rightSpace =
          viewBoxRect.x + viewBoxRect.width - selectedViewportPoint.x
        const leftSpace = selectedViewportPoint.x - viewBoxRect.x
        const preferredX =
          fitsRight || (!fitsLeft && rightSpace >= leftSpace) ? rightX : leftX

        return clamp(preferredX, minX, maxX)
      })()
    : 0
  const detailPanelY = selectedViewportPoint
    ? clamp(
        selectedViewportPoint.y - 24,
        viewBoxRect.y + 16,
        viewBoxRect.y + viewBoxRect.height - DETAIL_PANEL_HEIGHT - 16,
      )
    : 0

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
            height={DETAIL_PANEL_HEIGHT}
            width={DETAIL_PANEL_WIDTH}
            x={detailPanelX}
            y={detailPanelY}
          >
            <div
              aria-label={`${selectedNode.label}知识点详情`}
              className="pointer-events-auto h-full w-full overflow-y-auto overscroll-contain rounded-lg border border-[#7DA0CA]/40 bg-[#052659]/95 p-6 font-sans text-sm text-[#C1E8FF] shadow-2xl shadow-[#021024]/50 backdrop-blur"
              data-testid="knowledge-point-detail-panel"
              role="region"
              onPointerDown={(event) => event.stopPropagation()}
              onWheel={(event) => event.stopPropagation()}
            >
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <div className="text-lg font-semibold leading-6 text-white">
                    {selectedNode.label}
                  </div>
                  <div className="mt-1.5 text-sm text-[#7DA0CA]">
                    {difficultyLabel[selectedNode.difficulty_level] ??
                      selectedNode.difficulty_level}{' '}
                    / {statusLabel[selectedNode.status] ?? selectedNode.status}
                  </div>
                </div>
                <button
                  type="button"
                  className="flex size-7 shrink-0 items-center justify-center rounded border border-[#7DA0CA]/40 text-base text-[#C1E8FF] transition-colors hover:bg-[#021024] hover:text-white"
                  aria-label="关闭知识点详情"
                  onClick={() => onSelect(null)}
                >
                  ×
                </button>
              </div>

              <div className="mb-4">
                <div className="mb-2 flex justify-between text-sm text-[#7DA0CA]">
                  <span>掌握度</span>
                  <span>{Math.round(selectedNode.mastery_score)}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-[#C1E8FF]"
                    style={{
                      width: `${clamp(selectedNode.mastery_score, 0, 100)}%`,
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-md border border-white/10 bg-white/[0.04] p-3">
                  <div className="text-slate-500">置信度</div>
                  <div className="mt-1 font-medium text-white">
                    {Math.round(selectedNode.evidence_confidence * 100)}%
                  </div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.04] p-3">
                  <div className="text-slate-500">趋势</div>
                  <div className="mt-1 font-medium text-white">
                    {trendLabel[selectedNode.trend] ?? selectedNode.trend}
                  </div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.04] p-3">
                  <div className="text-slate-500">下一题正确率</div>
                  <div className="mt-1 font-medium text-white">
                    {Math.round(selectedNode.p_correct_next * 100)}%
                  </div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.04] p-3">
                  <div className="text-slate-500">模型</div>
                  <div className="mt-1 truncate font-medium text-white">
                    {selectedNode.model_version}
                  </div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.04] p-3">
                  <div className="text-slate-500">关系</div>
                  <div className="mt-1 font-medium text-white">
                    {predecessors.length + successors.length}
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm leading-6">
                <div className="line-clamp-2 text-[#7DA0CA]">
                  前置：
                  {predecessors.map((node) => node.label).join('、') || '无'}
                </div>
                <div className="line-clamp-2 text-[#7DA0CA]">
                  后续：
                  {successors.map((node) => node.label).join('、') || '无'}
                </div>
              </div>

              <div className="mt-4 border-t border-white/10 pt-3">
                <div className="mb-2 font-medium text-white">最近状态事件</div>
                {events.length > 0 ? (
                  <div className="space-y-2 pr-1">
                    {events.map((event) => (
                      <div
                        key={event.id}
                        className="rounded border border-white/10 bg-white/[0.04] p-2"
                      >
                        <div className="flex justify-between gap-3 text-xs text-[#7DA0CA]">
                          <span>
                            {Math.round(event.score_before)}% →{' '}
                            {Math.round(event.score_after)}%
                          </span>
                          <span>{event.model_version}</span>
                        </div>
                        <div className="mt-1 line-clamp-2 text-xs leading-5 text-[#C1E8FF]">
                          {event.explanation_summary ||
                            event.reason_codes.join('、') ||
                            '该事件已计入知识状态。'}
                        </div>
                        {event.algorithm === 'expert_bkt' && (
                          <div className="mt-2 space-y-2 border-t border-white/10 pt-2">
                            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                              <div className="rounded bg-[#021024]/70 px-2 py-1.5">
                                更新前{' '}
                                <span className="text-white">
                                  {event.prior_mastery == null
                                    ? '—'
                                    : `${Math.round(event.prior_mastery * 100)}%`}
                                </span>
                              </div>
                              <div className="rounded bg-[#021024]/70 px-2 py-1.5">
                                遗忘后{' '}
                                <span className="text-white">
                                  {event.prior_after_forgetting == null
                                    ? '—'
                                    : `${Math.round(event.prior_after_forgetting * 100)}%`}
                                </span>
                              </div>
                              <div className="rounded bg-[#021024]/70 px-2 py-1.5">
                                观察后{' '}
                                <span className="text-white">
                                  {event.posterior_after_observation == null
                                    ? '—'
                                    : `${Math.round(event.posterior_after_observation * 100)}%`}
                                </span>
                              </div>
                              <div className="rounded bg-[#021024]/70 px-2 py-1.5">
                                学习后{' '}
                                <span className="text-white">
                                  {event.posterior_after_learning == null
                                    ? '—'
                                    : `${Math.round(event.posterior_after_learning * 100)}%`}
                                </span>
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[#7DA0CA]">
                              <span>
                                证据权重 {event.event_weight.toFixed(2)}
                              </span>
                              {event.effective_parameters.learn_probability !=
                                null && (
                                <span>
                                  学习转移{' '}
                                  {Math.round(
                                    event.effective_parameters
                                      .learn_probability * 100,
                                  )}
                                  %
                                </span>
                              )}
                              {event.effective_parameters.slip_probability !=
                                null && (
                                <span>
                                  失误率{' '}
                                  {Math.round(
                                    event.effective_parameters
                                      .slip_probability * 100,
                                  )}
                                  %
                                </span>
                              )}
                              {event.effective_parameters.guess_probability !=
                                null && (
                                <span>
                                  猜测率{' '}
                                  {Math.round(
                                    event.effective_parameters
                                      .guess_probability * 100,
                                  )}
                                  %
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-[#7DA0CA]">
                    暂无状态变化事件。
                  </div>
                )}
              </div>
            </div>
          </foreignObject>
        )}
      </svg>

      <div
        aria-label="按知识点状态筛选"
        className="absolute left-4 top-4 flex max-w-[calc(100%-8rem)] flex-wrap gap-2 text-[11px] font-medium text-[#C1E8FF]"
        role="group"
      >
        <button
          type="button"
          aria-pressed={activeStatuses.size === 0}
          className={cn(
            'rounded-full border border-[#7DA0CA]/60 bg-[#021024]/80 px-2.5 py-1 backdrop-blur transition hover:bg-[#052659] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white',
            activeStatuses.size === 0 ? 'ring-2 ring-white/80' : 'opacity-60',
          )}
          onClick={onClearStatusFilters}
        >
          全部
        </button>
        {KNOWLEDGE_STATUS_OPTIONS.map((option) => {
          const isActive =
            activeStatuses.size === 0 || activeStatuses.has(option.value)
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isActive}
              className={cn(
                'rounded-full border px-2.5 py-1 backdrop-blur transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white',
                option.className,
                isActive
                  ? 'ring-1 ring-white/70'
                  : 'opacity-45 hover:opacity-80',
              )}
              data-testid={`knowledge-status-filter-${option.value}`}
              onClick={() => onStatusToggle(option.value)}
            >
              {option.label}
            </button>
          )
        })}
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
