import { describe, expect, it } from 'vitest'
import { createCourseQuizQuestionGroup } from './course-library'

describe('createCourseQuizQuestionGroup', () => {
  it('turns multiple choice questions into one quiz package', () => {
    const group = createCourseQuizQuestionGroup({
      quizId: 'quiz-1',
      quizName: '归并排序基础测验',
      projectId: 'project-1',
      projectName: '算法课程',
      questions: Array.from({ length: 9 }, (_, index) => ({
        knowledge_point_id: index < 5 ? 'merge-sort' : 'complexity',
      })),
    })

    expect(group).toMatchObject({
      id: 'quiz-1',
      resourceId: 'quiz-1',
      title: '归并排序基础测验',
      questionCount: 9,
      knowledgePointIds: ['merge-sort', 'complexity'],
    })
  })

  it('does not create an empty quiz package', () => {
    expect(
      createCourseQuizQuestionGroup({
        quizId: 'quiz-empty',
        quizName: '空测验',
        projectId: 'project-1',
        projectName: '算法课程',
        questions: [],
      }),
    ).toBeNull()
  })
})
