// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentRunsApi } from './agent-runs'

vi.mock('@/lib/auth-client', () => ({
  authClient: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  },
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('agentRunsApi.latest', () => {
  it('loads the newest persisted run for the selected project', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('null', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(agentRunsApi.latest('project / 1')).resolves.toBeNull()

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      '/api/v1/projects/project%20%2F%201/agent-runs/latest',
    )
  })
})
