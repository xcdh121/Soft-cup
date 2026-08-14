// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  SourceReadingStatus,
  shouldShowSourceReadingStatus,
} from './source-reading-status'
import type { ChatMessageDto } from '@/integrations/api/client'

const sourceMessage: ChatMessageDto = {
  id: 'assistant-1',
  chat_id: 'chat-1',
  role: 'assistant',
  created_at: '2026-08-14T08:00:00.000Z',
  parts: [
    {
      type: 'source-document',
      source_id: 'source-1',
      media_type: 'text/plain',
      title: 'Source 1',
      order: 0,
    },
  ],
}

describe('SourceReadingStatus', () => {
  it('renders three staggered animated dots', () => {
    const { container } = render(<SourceReadingStatus />)

    expect(
      screen.getByRole('status', {
        name: '已找到相关资料，正在阅读并组织回答…',
      }),
    ).toBeTruthy()
    const dots = container.querySelectorAll('[data-animated-dot]')
    expect(dots).toHaveLength(3)
    expect(Array.from(dots).map((dot) => dot.textContent)).toEqual([
      '.',
      '.',
      '.',
    ])
    expect(Array.from(dots).map((dot) => dot.getAttribute('style'))).toEqual([
      'animation-delay: -0.3s; animation-duration: 1s;',
      'animation-delay: -0.15s; animation-duration: 1s;',
      'animation-delay: 0s; animation-duration: 1s;',
    ])
  })

  it('only shows after sources arrive and before answer text starts', () => {
    expect(shouldShowSourceReadingStatus(sourceMessage, 'assistant-1')).toBe(
      true,
    )
    expect(shouldShowSourceReadingStatus(sourceMessage, 'assistant-2')).toBe(
      false,
    )
    expect(
      shouldShowSourceReadingStatus(
        {
          ...sourceMessage,
          parts: [
            ...(sourceMessage.parts ?? []),
            { type: 'text', text_content: '回答开始', order: 1 },
          ],
        },
        'assistant-1',
      ),
    ).toBe(false)
  })
})
