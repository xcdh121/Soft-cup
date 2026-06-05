import { KnowledgeGraphPage } from '@/features/knowledge-graph/knowledge-graph-page'
import { knowledgeGraphRoute } from '@/routes/_config'

export const KnowledgeGraphRoute = () => {
  const params = knowledgeGraphRoute.useParams()
  return <KnowledgeGraphPage projectId={params.projectId} />
}
