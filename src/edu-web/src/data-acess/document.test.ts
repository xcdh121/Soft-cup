// @vitest-environment jsdom

import { Registry } from '@effect-atom/atom-react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamDocumentQuestionAtom } from './document'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('document question streaming', () => {
  it('forwards text deltas and terminal citations from SSE', async () => {
    const projectId = '11111111-1111-4111-8111-111111111111'
    const documentId = '22222222-2222-4222-8222-222222222222'
    const encoder = new TextEncoder()
    const payload = [
      `data: ${JSON.stringify({ type: 'delta', content: '第一段' })}\n\n`,
      `data: ${JSON.stringify({ type: 'delta', content: '第二段' })}\n\n`,
      `data: ${JSON.stringify({
        type: 'citations',
        citations: [
          {
            document_id: documentId,
            segment_id: 'segment-1',
            title: '课程讲义',
            page_number: 3,
            score: null,
            excerpt: '引用内容',
          },
        ],
      })}\n\n`,
      'data: {"type":"done"}\n\n',
    ].join('')

    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        const midpoint = Math.floor(payload.length / 2)
        return Promise.resolve(
          new Response(
            new ReadableStream<Uint8Array>({
              start(controller) {
                controller.enqueue(encoder.encode(payload.slice(0, midpoint)))
                controller.enqueue(encoder.encode(payload.slice(midpoint)))
                controller.close()
              },
            }),
            {
              status: 200,
              headers: { 'Content-Type': 'text/event-stream' },
            },
          ),
        )
      }),
    )

    const onDelta = vi.fn()
    const onCitations = vi.fn()
    const streamAtom = streamDocumentQuestionAtom(documentId)
    const registry = Registry.make()
    registry.mount(streamAtom)
    registry.set(streamAtom, {
      projectId,
      documentId,
      question: '请解释这段内容',
      pageNumber: 3,
      onDelta,
      onCitations,
    })
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
    await vi.waitFor(() => {
      expect(onDelta.mock.calls.flat()).toEqual(['第一段', '第二段'])
      expect(onCitations).toHaveBeenCalledWith([
        expect.objectContaining({
          document_id: documentId,
          page_number: 3,
        }),
      ])
    })
    const [requestUrl, requestInit] = vi.mocked(fetch).mock.calls[0]
    expect(String(requestUrl)).toContain(`/documents/${documentId}/ask/stream`)
    expect(requestInit?.method).toBe('POST')

    registry.dispose()
  })
})
