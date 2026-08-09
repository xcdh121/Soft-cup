import type { KnowledgeGraph } from '@/data-acess/knowledge-graph'

export function filterKnowledgeGraph(
  graph: KnowledgeGraph,
  query: string,
  onlyWeak: boolean,
  activeStatuses: ReadonlySet<string>,
): KnowledgeGraph {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery && !onlyWeak && activeStatuses.size === 0) return graph

  const nodes = graph.nodes.filter((node) => {
    const matchesQuery =
      !normalizedQuery ||
      node.label.toLocaleLowerCase().includes(normalizedQuery) ||
      node.tags.some((tag) => tag.toLocaleLowerCase().includes(normalizedQuery))
    const matchesWeak = !onlyWeak || node.mastery_score < 60
    const matchesStatus =
      activeStatuses.size === 0 || activeStatuses.has(node.status)
    return matchesQuery && matchesWeak && matchesStatus
  })
  const nodeIds = new Set(nodes.map((node) => node.id))
  return {
    ...graph,
    nodes,
    edges: graph.edges.filter(
      (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
    ),
  }
}
