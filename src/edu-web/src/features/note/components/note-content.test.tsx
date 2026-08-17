// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { NoteContent } from './note-content'
import type { ReactNode } from 'react'

const { refreshNote } = vi.hoisted(() => ({
  refreshNote: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@effect-atom/atom-react', () => ({
  useAtomValue: vi.fn((atom: string) =>
    atom === 'note-progress' ? null : { state: 'success' },
  ),
  useAtomSet: vi.fn(() => refreshNote),
  Result: {
    isSuccess: vi.fn(() => true),
    builder: vi.fn(() => {
      const builder = {
        onInitialOrWaiting: vi.fn(() => builder),
        onFailure: vi.fn(() => builder),
        onSuccess: vi.fn((renderSuccess) => {
          builder.render = vi.fn(() =>
            renderSuccess({ content: '', description: null }),
          )
          return builder
        }),
        render: vi.fn(),
      }
      return builder
    }),
  },
}))

vi.mock('@/data-acess/note', () => ({
  noteAtom: vi.fn(() => 'note'),
  noteProgressAtom: 'note-progress',
  refreshNoteAtom: 'refresh-note',
}))

vi.mock('@/hooks/use-generated-note-stream', () => ({
  useGeneratedNoteStream: vi.fn(() => ({
    isGenerating: true,
    snapshot: {
      status: 'generating',
      content: '',
      description: null,
    },
  })),
}))

vi.mock('@/components/ai-elements/response', () => ({
  Response: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

describe('NoteContent', () => {
  it('shows only one status while the first streamed content is pending', () => {
    render(<NoteContent noteId="note-1" projectId="project-1" />)

    expect(
      screen.getAllByText('笔记模型正在准备，内容即将开始显示...'),
    ).toHaveLength(1)
    expect(
      screen.queryByText('笔记正在生成，内容会持续更新…'),
    ).toBeNull()
    expect(
      screen.queryByText('笔记正在排队生成，内容完成后会自动显示...'),
    ).toBeNull()
  })
})
