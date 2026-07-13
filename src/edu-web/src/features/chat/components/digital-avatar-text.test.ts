import { describe, expect, it } from 'vitest'
import { splitSpeechText } from './digital-avatar-text'

describe('splitSpeechText', () => {
  it('keeps every SDK payload below the configured limit', () => {
    const text = '测'.repeat(4001)
    const chunks = splitSpeechText(text)

    expect(chunks.map((chunk) => chunk.length)).toEqual([1800, 1800, 401])
    expect(chunks.join('')).toBe(text)
  })

  it('prefers a sentence boundary when one is available', () => {
    const text = `${'甲'.repeat(1000)}。${'乙'.repeat(1000)}`
    const chunks = splitSpeechText(text)

    expect(chunks).toHaveLength(2)
    expect(chunks[0].endsWith('。')).toBe(true)
    expect(chunks.every((chunk) => chunk.length <= 1800)).toBe(true)
  })
})
