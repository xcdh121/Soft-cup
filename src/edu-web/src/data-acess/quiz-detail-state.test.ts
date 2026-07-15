import { describe, expect, it } from 'vitest'
import { getQuizCorrectOption } from './quiz-detail-state'

const question = {
  correct_option: 'a',
  option_a: '稳定排序会保留相等元素的原始顺序',
  option_b: '排序后一定不会出现重复元素',
  option_c: '只适用于整数排序',
  option_d: '时间复杂度一定是 O(n)',
}

describe('getQuizCorrectOption', () => {
  it('normalizes lower-case option keys', () => {
    expect(getQuizCorrectOption(question)).toBe('A')
  })

  it('grades by option key even when the attached description differs', () => {
    expect(
      getQuizCorrectOption({
        ...question,
        correct_option: 'A. 这段描述与当前选项文案不一致',
      }),
    ).toBe('A')
  })

  it('maps a legacy answer description back to its option key', () => {
    expect(
      getQuizCorrectOption({
        ...question,
        correct_option: question.option_b,
      }),
    ).toBe('B')
  })

  it('does not treat an answer description starting with A as option A', () => {
    expect(
      getQuizCorrectOption({
        ...question,
        correct_option: 'A graph can contain cycles',
        option_b: 'A graph can contain cycles',
      }),
    ).toBe('B')
  })
})
