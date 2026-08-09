import { describe, expect, it } from 'vitest'
import { buildWeeklySchedule } from './study-plan'

describe('buildWeeklySchedule', () => {
  it('always returns a complete seven-day schedule', () => {
    const schedule = buildWeeklySchedule({
      path_steps: [
        { title: '完成第一项学习任务' },
        { title: '完成第二项学习任务' },
      ],
    })

    expect(schedule).toHaveLength(7)
    expect(schedule.map((day) => day.day)).toEqual([
      '第 1 天',
      '第 2 天',
      '第 3 天',
      '第 4 天',
      '第 5 天',
      '第 6 天',
      '第 7 天',
    ])
    expect(schedule.every((day) => day.tasks.length > 0)).toBe(true)
    expect(schedule[0].tasks[0]).toContain('完成第一项学习任务')
    expect(schedule[2].tasks[0]).toContain('回顾并强化')
    expect(schedule[2].tasks[0].length).toBeGreaterThan(60)
  })

  it('distributes paths longer than seven steps across the same week', () => {
    const schedule = buildWeeklySchedule({
      path_steps: Array.from({ length: 9 }, (_, index) => ({
        title: `学习任务 ${index + 1}`,
      })),
    })

    expect(schedule).toHaveLength(7)
    expect(schedule[0].tasks).toHaveLength(2)
    expect(schedule[0].tasks[0]).toContain('学习任务 1')
    expect(schedule[0].tasks[1]).toContain('学习任务 8')
    expect(schedule[1].tasks[0]).toContain('学习任务 2')
    expect(schedule[1].tasks[1]).toContain('学习任务 9')
  })

  it('uses the current knowledge point, reason and objective instead of fixed day copy', () => {
    const schedule = buildWeeklySchedule({
      title: '动态规划专项计划',
      based_on_knowledge_points: ['动态规划状态转移'],
      path_steps: [
        {
          title: '完成状态转移练习',
          reason: '近期练习显示状态定义仍不稳定。',
          objective: '能够独立写出状态定义和转移方程。',
          type: 'practice',
        },
      ],
    })

    expect(schedule[0].tasks[0]).toContain('动态规划状态转移')
    expect(schedule[0].tasks[0]).toContain('近期练习显示状态定义仍不稳定')
    expect(schedule[0].tasks[0]).toContain('独立写出状态定义和转移方程')
    expect(schedule[0].tasks[0]).toContain('错题对应的知识点')
  })
})
