import { useMemo, useState } from 'react'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Search, TrendingDown } from 'lucide-react'
import { filterKnowledgeGraph } from './filter-knowledge-graph'
import { KnowledgeGraphCanvas } from './knowledge-graph-canvas'
import type {
  KnowledgeGraph,
  KnowledgeGraphNode,
} from '@/data-acess/knowledge-graph'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  knowledgeGraphAtom,
  knowledgeStateEventsAtom,
} from '@/data-acess/knowledge-graph'
import { ProjectHeader } from '@/features/project/components/project-header'

function GraphContent({
  graph,
  projectId,
}: {
  graph: KnowledgeGraph
  projectId: string
}) {
  const [query, setQuery] = useState('')
  const [onlyWeak, setOnlyWeak] = useState(false)
  const [activeStatuses, setActiveStatuses] = useState<Set<string>>(new Set())
  const [selectedNode, setSelectedNode] = useState<KnowledgeGraphNode | null>(
    null,
  )
  const eventsResult = useAtomValue(
    knowledgeStateEventsAtom(
      selectedNode ? JSON.stringify([projectId, selectedNode.id]) : '',
    ),
  )
  const selectedEvents = Result.isSuccess(eventsResult)
    ? eventsResult.value
    : []

  const filteredGraph = useMemo(() => {
    return filterKnowledgeGraph(graph, query, onlyWeak, activeStatuses)
  }, [activeStatuses, graph, onlyWeak, query])

  const toggleStatus = (status: string) => {
    const nextStatuses = new Set(activeStatuses)
    if (nextStatuses.size === 0) {
      nextStatuses.add(status)
    } else if (nextStatuses.has(status)) {
      nextStatuses.delete(status)
    } else {
      nextStatuses.add(status)
    }
    setActiveStatuses(nextStatuses)
    if (
      nextStatuses.size > 0 &&
      selectedNode &&
      !nextStatuses.has(selectedNode.status)
    ) {
      setSelectedNode(null)
    }
  }

  const clearStatusFilters = () => {
    setActiveStatuses(new Set())
  }

  return (
    <section className="flex min-h-[720px] flex-col overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-sm">
      <div className="flex flex-col gap-4 border-b px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="font-semibold">知识网络</h2>
          <p className="text-xs text-muted-foreground">
            {filteredGraph.nodes.length} 个知识点，
            {filteredGraph.edges.length} 条关系
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索知识点或标签"
              className="pl-9"
            />
          </div>
          <Button
            type="button"
            variant={onlyWeak ? 'default' : 'outline'}
            onClick={() => setOnlyWeak((value) => !value)}
          >
            <TrendingDown className="h-4 w-4" />
            只看薄弱点
          </Button>
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <KnowledgeGraphCanvas
          activeStatuses={activeStatuses}
          graph={filteredGraph}
          selectedNodeId={selectedNode?.id ?? null}
          events={selectedEvents}
          onClearStatusFilters={clearStatusFilters}
          onSelect={setSelectedNode}
          onStatusToggle={toggleStatus}
        />
        {filteredGraph.nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            没有符合当前筛选条件的知识点，可点击“全部”恢复显示。
          </div>
        )}
      </div>
    </section>
  )
}

export const KnowledgeGraphPage = ({ projectId }: { projectId: string }) => {
  const graphResult = useAtomValue(knowledgeGraphAtom(projectId))

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-[1600px] flex-1 flex-col gap-6 px-4 py-6">
          {Result.builder(graphResult)
            .onSuccess((graph) => (
              <GraphContent graph={graph} projectId={projectId} />
            ))
            .onInitialOrWaiting(() => (
              <section className="rounded-2xl border bg-card p-8 text-sm text-muted-foreground shadow-sm">
                正在计算知识图谱布局...
              </section>
            ))
            .onFailure(() => (
              <section className="rounded-2xl border bg-card p-8 text-sm text-destructive shadow-sm">
                知识图谱加载失败。请确认项目已绑定课程，且知识图谱接口可用。
              </section>
            ))
            .render()}
        </div>
      </div>
    </div>
  )
}
