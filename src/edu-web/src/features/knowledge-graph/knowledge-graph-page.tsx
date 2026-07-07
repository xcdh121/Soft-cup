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
import { Progress } from '@/components/ui/progress'
import { knowledgeGraphAtom } from '@/data-acess/knowledge-graph'
import { ProjectHeader } from '@/features/project/components/project-header'
import { KnowledgeGraphCanvas } from './knowledge-graph-canvas'

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

  const predecessors = selectedNode
    ? graph.edges
        .filter((edge) => edge.target === selectedNode.id)
        .map((edge) => graph.nodes.find((node) => node.id === edge.source))
        .filter((node): node is KnowledgeGraphNode => Boolean(node))
    : []
  const successors = selectedNode
    ? graph.edges
        .filter((edge) => edge.source === selectedNode.id)
        .map((edge) => graph.nodes.find((node) => node.id === edge.target))
        .filter((node): node is KnowledgeGraphNode => Boolean(node))
    : []

  return (
    <section className="grid min-h-[680px] gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="flex min-h-[680px] flex-col overflow-hidden rounded-[24px] border bg-background shadow-sm">
        <div className="flex flex-col gap-3 border-b px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="font-semibold">先修知识结构</h2>
            <p className="text-xs text-muted-foreground">
              从左到右表示建议学习顺序，点击节点可高亮关联路径。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-52">
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
              onSelect={setSelectedNode}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              没有符合当前筛选条件的知识点。
            </div>
          )}
        </div>
      </div>

      <aside className="space-y-4">
        <section className="rounded-[24px] border bg-background p-5 shadow-sm">
          <h2 className="font-semibold">图谱概览</h2>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-muted/40 p-3">
              <div className="text-2xl font-semibold">{graph.nodes.length}</div>
              <div className="text-xs text-muted-foreground">知识点</div>
            </div>
            <div className="rounded-2xl bg-muted/40 p-3">
              <div className="text-2xl font-semibold">{graph.edges.length}</div>
              <div className="text-xs text-muted-foreground">先修关系</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
            <span className="rounded-full bg-slate-100 px-2 py-1">
              灰色 未学习
            </span>
            <span className="rounded-full bg-red-100 px-2 py-1">红色 薄弱</span>
            <span className="rounded-full bg-sky-100 px-2 py-1">
              蓝色 学习中
            </span>
            <span className="rounded-full bg-emerald-100 px-2 py-1">
              绿色 已掌握
            </span>
          </div>
        </section>

        <section className="rounded-[24px] border bg-background p-5 shadow-sm">
          {selectedNode ? (
            <div className="space-y-4">
              <div>
                <Badge variant="secondary">
                  {difficultyLabel[selectedNode.difficulty_level] ??
                    selectedNode.difficulty_level}
                </Badge>
                <h2 className="mt-2 text-lg font-semibold">
                  {selectedNode.label}
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  {statusLabel[selectedNode.status] ?? selectedNode.status} ·
                  趋势
                  {trendLabel[selectedNode.trend] ?? selectedNode.trend}
                </p>
              </div>
              <div>
                <div className="mb-2 flex justify-between text-sm">
                  <span>掌握度</span>
                  <strong>{Math.round(selectedNode.mastery_score)}%</strong>
                </div>
                <Progress value={selectedNode.mastery_score} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl bg-muted/40 p-3">
                  <div className="text-muted-foreground">前置知识</div>
                  <div className="mt-1 font-semibold">
                    {predecessors.length} 个
                  </div>
                </div>
                <div className="rounded-xl bg-muted/40 p-3">
                  <div className="text-muted-foreground">后续知识</div>
                  <div className="mt-1 font-semibold">
                    {successors.length} 个
                  </div>
                </div>
              </div>
              {predecessors.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-muted-foreground">
                    建议先掌握
                  </h3>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {predecessors.map((node) => (
                      <Badge key={node.id} variant="outline">
                        {node.label}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {selectedNode.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selectedNode.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="py-8 text-center text-sm text-muted-foreground">
              点击一个知识节点，查看掌握状态与先修关系。
            </div>
          )}
        </section>
      </aside>
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
          <section className="rounded-[28px] border bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-6 shadow-sm">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  知识图谱
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  从先修关系和个人掌握状态，找到下一步最值得学习的知识。
                </p>
              </div>
              <Badge variant="secondary" className="rounded-full px-3 py-1">
                {Result.isSuccess(graphResult)
                  ? `${graphResult.value.nodes.length} 个知识点`
                  : '加载中'}
              </Badge>
            </div>
          </section>

          {Result.builder(graphResult)
            .onSuccess((graph) => <GraphContent graph={graph} />)
            .onInitialOrWaiting(() => (
              <section className="rounded-[24px] border bg-background p-8 text-sm text-muted-foreground shadow-sm">
                正在计算知识图谱布局...
              </section>
            ))
            .onFailure(() => (
              <section className="rounded-[24px] border bg-background p-8 text-sm text-destructive shadow-sm">
                知识图谱加载失败。请确认项目已绑定课程，且知识图谱接口可用。
              </section>
            ))
            .render()}
        </div>
      </div>
    </div>
  )
}
