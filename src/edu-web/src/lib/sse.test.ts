import { describe, expect, it } from 'vitest'
import { appendSseChunk } from './sse'

describe('appendSseChunk', () => {
  it('keeps an incomplete SSE event until the next network chunk', () => {
    const first = appendSseChunk('', 'data: {"content":"Hel')
    expect(first.blocks).toEqual([])

    const second = appendSseChunk(
      first.buffer,
      'lo"}\n\ndata: {"done":true}\n\n',
    )
    expect(second.blocks).toEqual([
      'data: {"content":"Hello"}',
      'data: {"done":true}',
    ])
    expect(second.buffer).toBe('')
  })
})
