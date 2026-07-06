import { Result, useAtomValue } from '@effect-atom/atom-react'
import type { KnowledgeGraph } from '@/data-acess/knowledge-graph'
import { Badge } from '@/components/ui/badge'
import { knowledgeGraphAtom } from '@/data-acess/knowledge-graph'
import { ProjectHeader } from '@/features/project/components/project-header'
import { MindMapView } from '@/features/mind-map/components/mind-map-view'

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

const makeMapData = (graph: KnowledgeGraph) => {
  return {
    nodes: graph.nodes.map((node, index) => ({
      id: node.id,
      position: {
        x: (index % 4) * 220,
        y: Math.floor(index / 4) * 120,
      },
      data: {
        label: node.label,
        content: `${statusLabel[node.status] ?? node.status} · ${Math.round(
          node.mastery_score,
        )}%`,
      },
    })),
    edges: graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.relation_type,
    })),
  }
}

export const KnowledgeGraphPage = ({ projectId }: { projectId: string }) => {
  const graphResult = useAtomValue(knowledgeGraphAtom(projectId))

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="rounded-[28px] border bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-6 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-3">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    知识图谱
                  </h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    从课程知识点关系和学生掌握状态生成项目级知识结构。
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    真实 API 数据
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    知识点关系
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    掌握度状态
                  </Badge>
                </div>
              </div>

              <div className="rounded-2xl border bg-white/80 px-4 py-3 text-sm text-muted-foreground">
                当前状态
                <div className="mt-1 text-lg font-semibold text-foreground">
                  {Result.isSuccess(graphResult)
                    ? `${graphResult.value.nodes.length} 个知识点`
                    : '等待图谱数据'}
                </div>
              </div>
            </div>
          </section>

          {Result.builder(graphResult)
            .onSuccess((graph) => {
              const mapData = makeMapData(graph)
              const weakPoints = [...graph.nodes]
                .sort((a, b) => a.mastery_score - b.mastery_score)
                .slice(0, 5)

              return (
                <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
                  <div className="min-h-[640px] rounded-[24px] border bg-background shadow-sm">
                    <div className="border-b px-6 py-4">
                      <h2 className="text-lg font-semibold">图谱结构</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        节点来自课程知识点，连线来自知识点关系表。
                      </p>
                    </div>
                    <div className="h-[560px]">
                      <MindMapView mapData={mapData} />
                    </div>
                  </div>

                  <div className="space-y-6">
                    <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                      <h2 className="text-lg font-semibold">图谱概览</h2>
                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="rounded-2xl bg-muted/40 p-4">
                          <div className="text-2xl font-semibold">
                            {graph.nodes.length}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            知识点
                          </div>
                        </div>
                        <div className="rounded-2xl bg-muted/40 p-4">
                          <div className="text-2xl font-semibold">
                            {graph.edges.length}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            关系
                          </div>
                        </div>
                      </div>
                    </section>

                    <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                      <h2 className="text-lg font-semibold">薄弱知识点</h2>
                      <div className="mt-4 space-y-3">
                        {weakPoints.map((node) => (
                          <div
                            key={node.id}
                            className="rounded-2xl border bg-muted/20 p-4"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="font-medium">{node.label}</div>
                              <Badge variant="outline">
                                {Math.round(node.mastery_score)}%
                              </Badge>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>
                                {difficultyLabel[node.difficulty_level] ??
                                  node.difficulty_level}
                              </span>
                              <span>
                                {statusLabel[node.status] ?? node.status}
                              </span>
                              <span>
                                趋势：
                                {trendLabel[node.trend] ?? node.trend}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                      <h2 className="text-lg font-semibold">关系说明</h2>
                      <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                        {graph.edges.length === 0 ? (
                          <p>当前课程还没有知识点关系。</p>
                        ) : (
                          graph.edges.slice(0, 6).map((edge) => (
                            <p key={edge.id}>
                              {edge.source} → {edge.target}：
                              {edge.description ?? edge.relation_type}
                            </p>
                          ))
                        )}
                      </div>
                    </section>
                  </div>
                </section>
              )
            })
            .onInitialOrWaiting(() => (
              <section className="rounded-[24px] border bg-background p-8 text-sm text-muted-foreground shadow-sm">
                正在加载知识图谱...
              </section>
            ))
            .onFailure(() => (
              <section className="rounded-[24px] border bg-background p-8 text-sm text-destructive shadow-sm">
                知识图谱加载失败。请确认项目已经绑定课程，并且后端
                `/api/v1/projects/{'{project_id}'}/knowledge-graph` 接口可用。
              </section>
            ))
            .render()}
        </div>
      </div>
    </div>
  )
}
