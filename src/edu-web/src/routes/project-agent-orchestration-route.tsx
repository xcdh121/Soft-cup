import { AgentOrchestrationRoute } from '@/routes/agent-orchestration-route'
import { projectAgentOrchestrationRoute } from '@/routes/_config'

export const ProjectAgentOrchestrationRoute = () => {
  const params = projectAgentOrchestrationRoute.useParams()
  return <AgentOrchestrationRoute projectId={params.projectId} />
}
