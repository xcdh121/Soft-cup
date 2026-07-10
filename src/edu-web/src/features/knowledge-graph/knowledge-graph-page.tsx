import { useMemo, useState } from 'react'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Search, TrendingDown } from 'lucide-react'
import type {
  KnowledgeGraph,
  KnowledgeGraphNode,
} from '@/data-acess/knowledge-graph'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { knowledgeGraphAtom } from '@/data-acess/knowledge-graph'
import { ProjectHeader } from '@/features/project/components/project-header'
import { KnowledgeGraphCanvas } from './knowledge-graph-canvas'

function GraphContent({ graph }: { graph: KnowledgeGraph }) {
  const [query, setQuery] = useState('')
  const [onlyWeak, setOnlyWeak] = useState(false)
  const [selectedNode, setSelectedNode] = useState<KnowledgeGraphNode | null>(
    null,
  )

  const filteredGraph = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    if (!normalizedQuery && !onlyWeak) return graph

    const nodes = graph.nodes.filter((node) => {
      const matchesQuery =
        !normalizedQuery ||
        node.label.toLocaleLowerCase().includes(normalizedQuery) ||
        node.tags.some((tag) =>
          tag.toLocaleLowerCase().includes(normalizedQuery),
        )
      const matchesWeak = !onlyWeak || node.mastery_score < 60
      return matchesQuery && matchesWeak
    })
    const nodeIds = new Set(nodes.map((node) => node.id))
    return {
      ...graph,
      nodes,
      edges: graph.edges.filter(
        (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
      ),
    }
  }, [graph, onlyWeak, query])

  return (
    <section className="flex min-h-[720px] flex-col overflow-hidden rounded-2xl border bg-background shadow-sm">
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
        {filteredGraph.nodes.length > 0 ? (
          <KnowledgeGraphCanvas
            graph={filteredGraph}
            selectedNodeId={selectedNode?.id ?? null}
            onSelect={setSelectedNode}
          />
        ) : (
          <div className="flex h-full min-h-[620px] items-center justify-center text-sm text-muted-foreground">
            没有符合当前筛选条件的知识点。
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
          <section className="rounded-2xl border bg-background p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  知识图谱
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  从先修关系和个人掌握状态中找到下一步最值得学习的知识。
                </p>
              </div>
              <Badge
                variant="secondary"
                className="w-fit rounded-full px-3 py-1"
              >
                {Result.isSuccess(graphResult)
                  ? `${graphResult.value.nodes.length} 个知识点`
                  : '加载中'}
              </Badge>
            </div>
          </section>

          {Result.builder(graphResult)
            .onSuccess((graph) => <GraphContent graph={graph} />)
            .onInitialOrWaiting(() => (
              <section className="rounded-2xl border bg-background p-8 text-sm text-muted-foreground shadow-sm">
                正在计算知识图谱布局...
              </section>
            ))
            .onFailure(() => (
              <section className="rounded-2xl border bg-background p-8 text-sm text-destructive shadow-sm">
                知识图谱加载失败。请确认项目已绑定课程，且知识图谱接口可用。
              </section>
            ))
            .render()}
        </div>
      </div>
    </div>
  )
}
