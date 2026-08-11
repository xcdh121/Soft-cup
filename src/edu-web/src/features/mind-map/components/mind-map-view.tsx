import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Circle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// --- Types ---

export interface MindMapNodeData {
  id: string
  label: string
  content?: string
  children?: Array<MindMapNodeData>
}

type RawMindMapNode = Record<string, unknown>
type RawMindMapEdge = Record<string, unknown>

export type NormalizedMindMapData = {
  nodes: Array<{
    id: string
    data: { label: string; content?: string; [key: string]: unknown }
    position: { x: number; y: number }
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    label?: string | null
  }>
}

const asRecord = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : {}

const firstText = (...values: Array<unknown>) =>
  values
    .find((value): value is string =>
      Boolean(typeof value === 'string' && value.trim()),
    )
    ?.trim()

/** Normalize current, streamed, and legacy mind-map payloads before rendering. */
export const normalizeMindMapData = (
  mapData: unknown,
): NormalizedMindMapData => {
  const outer = asRecord(mapData)
  // Resource-package entries persist the graph under `content_json.map_data`,
  // while standalone and legacy mind maps store `nodes`/`edges` directly.
  const nestedMapData = asRecord(outer.map_data)
  const root =
    Array.isArray(nestedMapData.nodes) || Array.isArray(nestedMapData.edges)
      ? nestedMapData
      : outer
  const rawNodes = Array.isArray(root.nodes)
    ? (root.nodes as Array<RawMindMapNode>)
    : []
  const rawEdges = Array.isArray(root.edges)
    ? (root.edges as Array<RawMindMapEdge>)
    : []

  const seenNodeIds = new Set<string>()
  const nodes = rawNodes.flatMap((rawNode, index) => {
    const node = asRecord(rawNode)
    const data = asRecord(node.data)
    const id = String(node.id ?? '').trim()
    if (!id || seenNodeIds.has(id)) return []
    seenNodeIds.add(id)

    const label = firstText(
      data.label,
      node.label,
      data.title,
      node.title,
      data.text,
      node.text,
      data.name,
      node.name,
    )
    const position = asRecord(node.position)

    return [
      {
        id,
        data: {
          ...data,
          label: label ?? `节点 ${index + 1}`,
          content: firstText(data.content, data.detail, node.content),
        },
        position: {
          x: Number.isFinite(Number(position.x)) ? Number(position.x) : 0,
          y: Number.isFinite(Number(position.y)) ? Number(position.y) : 0,
        },
      },
    ]
  })

  const nodeIds = new Set(nodes.map((node) => node.id))
  const seenEdges = new Set<string>()
  const edges = rawEdges.flatMap((rawEdge, index) => {
    const edge = asRecord(rawEdge)
    const source = String(edge.source ?? '').trim()
    const target = String(edge.target ?? '').trim()
    if (
      !source ||
      !target ||
      source === target ||
      !nodeIds.has(source) ||
      !nodeIds.has(target)
    ) {
      return []
    }

    const relationship = `${source}\u0000${target}`
    if (seenEdges.has(relationship)) return []
    seenEdges.add(relationship)

    return [
      {
        id: String(edge.id ?? `edge-${index + 1}`),
        source,
        target,
        label: firstText(edge.label) ?? null,
      },
    ]
  })

  return { nodes, edges }
}

// Helper function to convert nodes/edges format to hierarchical tree
export function convertMindMapToTree(
  nodes: Array<{
    id: string
    data: { label: string; [key: string]: unknown }
    position?: { x: number; y: number }
  }>,
  edges: Array<{
    id: string
    source: string
    target: string
    label?: string | null
  }>,
): MindMapNodeData | null {
  if (nodes.length === 0) {
    return null
  }

  // Build a map of node ID to node data.
  const nodeMap = new Map<string, MindMapNodeData>()
  const childrenMap = new Map<string, Array<string>>()

  // Initialize all nodes
  nodes.forEach((node) => {
    nodeMap.set(node.id, {
      id: node.id,
      label: node.data.label,
      content: node.data.content as string | undefined,
      children: [],
    })
    childrenMap.set(node.id, [])
  })

  // Build parent-child relationships from edges
  edges.forEach((edge) => {
    const children = childrenMap.get(edge.source) || []
    children.push(edge.target)
    childrenMap.set(edge.source, children)
  })

  // Build a safe spanning tree. AI output can contain cross-links or cycles;
  // those relationships should not make the entire view recurse forever.
  const attachedNodeIds = new Set<string>()
  const buildNode = (
    nodeId: string,
    ancestors = new Set<string>(),
  ): MindMapNodeData | null => {
    const node = nodeMap.get(nodeId)
    if (!node || ancestors.has(nodeId) || attachedNodeIds.has(nodeId))
      return null

    attachedNodeIds.add(nodeId)
    const nextAncestors = new Set(ancestors)
    nextAncestors.add(nodeId)

    const childIds = childrenMap.get(nodeId) || []
    return {
      ...node,
      children: childIds
        .map((childId) => buildNode(childId, nextAncestors))
        .filter((child): child is MindMapNodeData => child !== null),
    }
  }

  // Find root nodes (nodes that are not targets of any edge)
  const targetIds = new Set(edges.map((e) => e.target))
  const rootNodes = nodes.filter((node) => !targetIds.has(node.id))

  const orderedRoots = [
    ...rootNodes,
    ...nodes.filter((node) => targetIds.has(node.id)),
  ]
  const forest = orderedRoots
    .map((node) => buildNode(node.id))
    .filter((node): node is MindMapNodeData => node !== null)

  if (forest.length > 1) {
    const syntheticRoot: MindMapNodeData = {
      id: 'root',
      label: '思维导图',
      children: forest,
    }
    return syntheticRoot
  }

  return forest[0] ?? null
}

// --- Recursive Node Component ---

const MindMapNode = ({
  data,
  depth = 0,
}: {
  data: MindMapNodeData
  depth?: number
}) => {
  const [isExpanded, setIsExpanded] = useState(true)
  const hasChildren = data.children && data.children.length > 0
  const isRoot = depth === 0

  return (
    <div className="flex flex-row items-center">
      {/* The Node Card */}
      <div className="relative flex items-center z-10">
        <div
          className={cn(
            'group flex items-center gap-2 border rounded-xl transition-all duration-200 shadow-sm',
            isRoot
              ? 'bg-card text-card-foreground px-6 py-4 border-primary/30'
              : 'bg-card text-card-foreground px-4 py-2 hover:border-primary/50 hover:shadow-md',
          )}
        >
          {/* Collapse Toggle Button */}
          {hasChildren && (
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'h-5 w-5 shrink-0',
                isRoot &&
                  'absolute -right-3 top-1/2 -translate-y-1/2 bg-background border shadow-sm',
              )}
              onClick={(e) => {
                e.stopPropagation()
                setIsExpanded(!isExpanded)
              }}
              aria-label={isExpanded ? '折叠' : '展开'}
            >
              {isExpanded ? (
                isRoot ? (
                  <ChevronRight className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 rotate-[-90deg]" />
                )
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </Button>
          )}

          {!hasChildren && !isRoot && (
            <Circle size={8} className="text-primary fill-current shrink-0" />
          )}

          <div className="flex flex-col min-w-0">
            <span
              className={cn(
                'font-medium break-words',
                isRoot ? 'text-lg text-foreground' : 'text-sm text-foreground',
              )}
            >
              {data.label}
            </span>
            {data.content && isRoot && (
              <span className="text-xs text-muted-foreground mt-1 max-w-[200px] truncate">
                {data.content}
              </span>
            )}
          </div>
        </div>

        {/* Connector Line to Children Group */}
        {hasChildren && isExpanded && <div className="w-8 h-px bg-border" />}
      </div>

      {/* Recursive Children Rendering */}
      {hasChildren && isExpanded && (
        <div className="flex flex-col gap-4 ml-0 border-l border-border pl-8 py-2 relative">
          {data.children?.map((child, index) => (
            <div key={child.id} className="relative">
              {/* Horizontal connector line */}
              <div className="absolute -left-8 top-1/2 w-8 h-px bg-border" />

              {/* Vertical Line Cover (to stop line going past last child or before first) */}
              {index === 0 && (
                <div className="absolute -left-[33px] -top-4 h-1/2 w-1 bg-background" />
              )}
              {index === data.children!.length - 1 && (
                <div className="absolute -left-[33px] top-1/2 h-full w-1 bg-background" />
              )}

              <MindMapNode data={child} depth={depth + 1} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- Main Container Component ---

type MindMapViewProps = {
  mapData: unknown
}

export const MindMapView = ({ mapData }: MindMapViewProps) => {
  const normalizedMapData = useMemo(
    () => normalizeMindMapData(mapData),
    [mapData],
  )
  const rootNode = useMemo(() => {
    return convertMindMapToTree(
      normalizedMapData.nodes,
      normalizedMapData.edges,
    )
  }, [normalizedMapData])

  if (!rootNode) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>没有可用的思维导图数据</p>
      </div>
    )
  }

  return (
    <div className="h-full w-full overflow-auto bg-background">
      <div className="min-w-full flex flex-col p-8">
        <div className="flex items-center justify-start">
          <MindMapNode data={rootNode} />
        </div>
      </div>
    </div>
  )
}
