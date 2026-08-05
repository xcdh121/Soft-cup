import { authClient } from '@/lib/auth-client'
import { env } from '@/env'

export type AgentRunStatus =
  | 'queued'
  | 'pending'
  | 'running'
  | 'waiting_external'
  | 'partially_completed'
  | 'completed'
  | 'cancelled'
  | 'failed'

export type AgentRun = {
  run_id: string
  project_id: string
  goal: string
  status: AgentRunStatus
  final_result: Record<string, unknown>
  current_agent_name: string | null
  heartbeat_at: string | null
  duration_ms: number | null
  model_name: string | null
  input_tokens: number
  output_tokens: number
  estimated_cost_micros: number
  trace_id: string | null
  retry_of_run_id: string | null
  orchestration_version: string
  failure_code: string | null
  last_event_sequence: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export type AgentRunStep = {
  step_id: string
  run_id: string
  node_id: string
  agent_name: string
  status: AgentRunStatus | 'skipped'
  depends_on: Array<string>
  attempt_count: number
  max_attempts: number
  optional: boolean
  error_code: string | null
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  heartbeat_at: string | null
  duration_ms: number | null
}

export type AgentRunEvent = {
  event_type: string
  run_id: string
  agent_name: string | null
  status: AgentRunStatus
  summary: string
  timestamp: string
  payload: Record<string, unknown>
  sequence: number
}

const baseUrl = env.VITE_SERVER_URL ?? window.location.origin

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const { data } = await authClient.auth.getSession()
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(data.session
        ? { Authorization: `Bearer ${data.session.access_token}` }
        : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string
    } | null
    throw new Error(payload?.detail || `请求失败（${response.status}）`)
  }
  return (await response.json()) as T
}

export const agentRunsApi = {
  get: (runId: string) =>
    request<AgentRun>(`/api/v1/agent-runs/${encodeURIComponent(runId)}`),
  steps: (runId: string) =>
    request<Array<AgentRunStep>>(
      `/api/v1/agent-runs/${encodeURIComponent(runId)}/steps`,
    ),
  events: (runId: string, afterSequence = 0) =>
    request<Array<AgentRunEvent>>(
      `/api/v1/agent-runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`,
    ),
  create: (projectId: string, goal: string) =>
    request<AgentRun>(
      `/api/v1/projects/${encodeURIComponent(projectId)}/agent-runs`,
      {
        method: 'POST',
        body: JSON.stringify({
          goal,
          idempotency_key: `${projectId}:${goal}:${crypto.randomUUID()}`,
        }),
      },
    ),
  cancel: (runId: string) =>
    request<AgentRun>(
      `/api/v1/agent-runs/${encodeURIComponent(runId)}/cancel`,
      { method: 'POST', body: '{}' },
    ),
  retry: (runId: string) =>
    request<AgentRun>(
      `/api/v1/agent-runs/${encodeURIComponent(runId)}/retry`,
      { method: 'POST', body: JSON.stringify({ mode: 'resume_failed' }) },
    ),
  streamUrl: (runId: string, afterSequence: number) =>
    `${baseUrl}/api/v1/agent-runs/${encodeURIComponent(runId)}/stream?after_sequence=${afterSequence}`,
  accessToken: async () => {
    const { data } = await authClient.auth.getSession()
    return data.session?.access_token ?? null
  },
}
