import { describe, expect, it } from 'vitest'
import { resolveChatAttachmentUrl } from './chat-image-attachment'

describe('resolveChatAttachmentUrl', () => {
  it('keeps temporary image previews intact', () => {
    expect(resolveChatAttachmentUrl('data:image/png;base64,AA==')).toBe(
      'data:image/png;base64,AA==',
    )
    expect(resolveChatAttachmentUrl('blob:http://localhost/image-id')).toBe(
      'blob:http://localhost/image-id',
    )
  })

  it('points persisted chat files at the API server', () => {
    expect(
      resolveChatAttachmentUrl(
        '/api/v1/projects/project-1/chats/chat-1/files/image.png',
      ),
    ).toContain('/api/v1/projects/project-1/chats/chat-1/files/image.png')
  })
})
