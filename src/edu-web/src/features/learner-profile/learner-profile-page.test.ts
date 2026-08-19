import { describe, expect, it } from 'vitest'
import { buildRecentPracticeSummary } from './learner-profile-page'

const localIso = (year: number, month: number, day: number, hour = 12) =>
  new Date(year, month - 1, day, hour).toISOString()

describe('buildRecentPracticeSummary', () => {
  it('calculates the recent seven-day accuracy from actual practice records', () => {
    const records = [
      ...Array.from({ length: 19 }, (_, index) => ({
        created_at: localIso(2026, 8, 19, index % 20),
        was_correct: index < 4,
      })),
      ...Array.from({ length: 10 }, (_, index) => ({
        created_at: localIso(2026, 8, 18, index),
        was_correct: index === 0,
      })),
      {
        created_at: localIso(2026, 8, 16),
        was_correct: false,
      },
      {
        created_at: localIso(2026, 8, 11),
        was_correct: true,
      },
    ]

    const summary = buildRecentPracticeSummary(
      records,
      new Date(2026, 7, 19, 12),
    )

    expect(summary.recentAttempts).toBe(30)
    expect(summary.recentAccuracy).toBe(17)
    expect(summary.dailyPractice.map((day) => day.attempts)).toEqual([
      0, 0, 0, 1, 0, 10, 19,
    ])
  })

  it('returns no accuracy only when the seven-day window is truly empty', () => {
    const summary = buildRecentPracticeSummary(
      [
        {
          created_at: localIso(2026, 8, 11),
          was_correct: true,
        },
      ],
      new Date(2026, 7, 19, 12),
    )

    expect(summary.recentAttempts).toBe(0)
    expect(summary.recentAccuracy).toBeNull()
  })
})
