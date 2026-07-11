import { Handle, Position } from '@xyflow/react'
import { ArrowDown, ArrowRight, ArrowUp } from 'lucide-react'
import type { Node, NodeProps } from '@xyflow/react'
import type { KnowledgeGraphNode } from '@/data-acess/knowledge-graph'
import { cn } from '@/lib/utils'

export type KnowledgeNodeData = KnowledgeGraphNode & {
  isDimmed: boolean
  isPath: boolean
}

export type KnowledgeFlowNode = Node<KnowledgeNodeData, 'knowledge'>

const trendIcon = {
  up: ArrowUp,
  stable: ArrowRight,
  down: ArrowDown,
}

const getMasteryStyle = (score: number, status: string) => {
  if (status === 'not_started') return 'border-[#7DA0CA] bg-[#C1E8FF]/25'
  if (score < 40) return 'border-[#5483B3] bg-[#C1E8FF]/40'
  if (score < 80) return 'border-[#052659] bg-[#C1E8FF]/55'
  return 'border-[#021024] bg-[#C1E8FF]/70'
}

export function KnowledgeNode({
  data,
  selected,
}: NodeProps<KnowledgeFlowNode>) {
  const TrendIcon =
    trendIcon[data.trend as keyof typeof trendIcon] ?? ArrowRight

  return (
    <div
      className={cn(
        'w-56 rounded-2xl border-2 px-4 py-3 shadow-sm transition-all',
        getMasteryStyle(data.mastery_score, data.status),
        selected && 'ring-2 ring-primary ring-offset-2',
        data.isPath && 'border-primary shadow-md',
        data.isDimmed && 'opacity-25',
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="flex items-start justify-between gap-2">
        <div className="line-clamp-2 text-sm font-semibold leading-5">
          {data.label}
        </div>
        <div className="flex shrink-0 items-center gap-1 text-xs font-semibold">
          <TrendIcon className="h-3.5 w-3.5" />
          {Math.round(data.mastery_score)}%
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/10">
        <div
          className="h-full rounded-full bg-current text-primary transition-all"
          style={{
            width: `${Math.max(0, Math.min(100, data.mastery_score))}%`,
          }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{data.difficulty_level}</span>
        <span>置信度 {Math.round(data.confidence * 100)}%</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  )
}
