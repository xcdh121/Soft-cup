// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest'
import { Registry } from '@effect-atom/atom-react'
import { Option } from 'effect'
import {
  buildQuizPracticeRecord,
  getQuizCorrectOption,
  persistQuizDetailProgress,
  quizDetailStateAtom,
  readQuizDetailProgress,
} from './quiz-detail-state'

const question = {
  correct_option: 'a',
  option_a: '稳定排序会保留相等元素的原始顺序',
  option_b: '排序后一定不会出现重复元素',
  option_c: '只适用于整数排序',
  option_d: '时间复杂度一定是 O(n)',
}

afterEach(() => sessionStorage.clear())

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

  it('restores an unfinished attempt after a page reload', () => {
    persistQuizDetailProgress('quiz-greedy', {
      currentQuestionIndex: 2,
      showResults: false,
      pendingPracticeRecords: {},
      selectedByQuestionId: {
        'question-1': 'A',
        'question-2': 'C',
        'question-3': 'B',
      },
      submittedByQuestionId: {
        'question-1': true,
        'question-2': true,
      },
    })

    expect(readQuizDetailProgress('quiz-greedy')).toEqual({
      currentQuestionIndex: 2,
      showResults: false,
      pendingPracticeRecords: {},
      selectedByQuestionId: {
        'question-1': 'A',
        'question-2': 'C',
        'question-3': 'B',
      },
      submittedByQuestionId: {
        'question-1': true,
        'question-2': true,
      },
    })

    const registryAfterReload = Registry.make()
    const restoredState = registryAfterReload.get(
      quizDetailStateAtom('quiz-greedy'),
    )
    expect(Option.getOrNull(restoredState)).toEqual(
      readQuizDetailProgress('quiz-greedy'),
    )
    registryAfterReload.dispose()
  })

  it('ignores corrupted saved progress instead of breaking the quiz page', () => {
    sessionStorage.setItem('edu.quiz-progress.v1:quiz-broken', '{broken')

    expect(readQuizDetailProgress('quiz-broken')).toBeNull()
  })

  it('stores quiz ids in metadata instead of the generated-resource foreign key', () => {
    const record = buildQuizPracticeRecord({
      question: {
        id: 'question-1',
        quiz_id: 'quiz-study-plan',
        project_id: 'project-1',
        knowledge_point_id: 'kp-1',
        question_text: '测试题目',
        ...question,
        explanation: undefined,
        difficulty_level: 'medium',
        position: 0,
        created_at: '2026-08-09T00:00:00Z',
      },
      userAnswer: 'A',
      quizId: 'quiz-study-plan',
      verification: null,
    })

    expect(record).not.toHaveProperty('resource_id')
    expect(record.metadata).toEqual({ quiz_id: 'quiz-study-plan' })
  })
})
