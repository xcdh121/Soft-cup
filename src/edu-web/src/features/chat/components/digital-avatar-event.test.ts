import { describe, expect, it } from 'vitest'
import {
  getAvatarEventStatus,
  getAvatarEventText,
} from './digital-avatar-event'

describe('digital avatar event parsing', () => {
  it('reads the cleaned SDK NLP display content', () => {
    expect(
      getAvatarEventText({
        content: '原始回答',
        displayContent: '适合展示的回答',
      }),
    ).toBe('适合展示的回答')
  })

  it('reads nested answer text and JSON event strings', () => {
    expect(
      getAvatarEventText({
        payload: { nlp: { answer: { text: '二叉树讲解' } } },
      }),
    ).toBe('二叉树讲解')
    expect(getAvatarEventText('{"asr":{"text":"如何上传文档"}}')).toBe(
      '如何上传文档',
    )
  })

  it('ignores event metadata that is not answer text', () => {
    expect(getAvatarEventText({ sid: 'session-id', status: 2 })).toBe('')
    expect(getAvatarEventStatus({ status: 2 })).toBe(2)
  })
})
