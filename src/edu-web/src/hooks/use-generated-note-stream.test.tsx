// @vitest-environment jsdom

import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useGeneratedNoteStream } from './use-generated-note-stream'

vi.mock('@/lib/auth-client', () => ({
  authClient: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'note-stream-token' } },
      }),
    },
  },
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useGeneratedNoteStream', () => {
  it('authenticates the note SSE request and applies streamed snapshots', async () => {
    const payload = {
      event: 'note_snapshot',
      resource_id: 'resource-1',
      note_id: 'note-1',
      status: 'completed',
      title: 'Streaming note',
      description: null,
      content: '# Streamed content',
      updated_at: '2026-08-17T00:00:00Z',
    }
    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode(`data: ${JSON.stringify(payload)}\n\n`),
        })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() =>
      useGeneratedNoteStream({ projectId: 'project-1', noteId: 'note-1' }),
    )

    await waitFor(() => {
      expect(result.current.snapshot?.content).toBe('# Streamed content')
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({
      Accept: 'text/event-stream',
      Authorization: 'Bearer note-stream-token',
    })
  })
})
