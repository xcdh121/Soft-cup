import { describe, expect, it } from 'vitest'
import { splitRadarLabel } from './learning-evaluation-page'

describe('splitRadarLabel', () => {
  it('keeps every character while wrapping long knowledge-point labels', () => {
    const label = '时间与空间复杂度综合分析'
    const lines = splitRadarLabel(label, 6)

    expect(lines.length).toBeGreaterThan(1)
    expect(lines.join('')).toBe(label)
    expect(lines.every((line) => Array.from(line).length <= 6)).toBe(true)
  })
})
