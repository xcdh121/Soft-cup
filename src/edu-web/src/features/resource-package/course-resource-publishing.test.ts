import { describe, expect, it } from 'vitest'
import { resolveCoursePublishTarget } from './course-resource-publishing'
import type { ProjectCourseOutline } from '@/data-acess/course-library'
import type { GeneratedResource } from '@/data-acess/resource-package'

const outline: ProjectCourseOutline = {
  courseId: 'course-1',
  chapters: [],
  knowledgePoints: [
    {
      id: 'merge-sort',
      course_id: 'course-1',
      chapter_id: 'sorting',
      name: '归并排序',
      description: null,
      difficulty_level: 'intermediate',
      position: 1,
      tags: ['merge-sort'],
      created_at: '',
      updated_at: '',
    },
    {
      id: 'quick-sort',
      course_id: 'course-1',
      chapter_id: 'sorting',
      name: '快速排序',
      description: null,
      difficulty_level: 'intermediate',
      position: 2,
      tags: ['quick-sort'],
      created_at: '',
      updated_at: '',
    },
  ],
}

const resource = (overrides: Partial<GeneratedResource>) =>
  ({
    id: 'resource-1',
    resource_package_id: 'package-1',
    project_id: 'project-1',
    user_id: 'user-1',
    resource_type: 'lecture_note',
    title: '排序算法讲义',
    summary: null,
    status: 'completed',
    format: 'markdown',
    content_text: null,
    content_json: null,
    file_url: null,
    preview_url: null,
    cover_image_url: null,
    source_document_ids: [],
    knowledge_point_ids: ['merge-sort', 'quick-sort'],
    difficulty_level: 'intermediate',
    estimated_minutes: 10,
    version: 1,
    generation_order: 1,
    generator_agent: null,
    generation_reason: null,
    error_message: null,
    created_at: '',
    updated_at: '',
    completed_at: '',
    ...overrides,
  }) satisfies GeneratedResource

describe('resolveCoursePublishTarget', () => {
  it('uses the matching knowledge point instead of attaching to every id', () => {
    expect(
      resolveCoursePublishTarget(
        resource({ title: '归并排序：从分治到合并' }),
        outline,
      )?.id,
    ).toBe('merge-sort')
  })

  it('uses the only available knowledge point directly', () => {
    expect(
      resolveCoursePublishTarget(
        resource({ knowledge_point_ids: ['quick-sort'] }),
        outline,
      )?.id,
    ).toBe('quick-sort')
  })

  it('leaves an ambiguous resource for manual assignment', () => {
    expect(resolveCoursePublishTarget(resource({}), outline)).toBeNull()
  })

  it('does not misclassify a resource from incidental words in its body', () => {
    expect(
      resolveCoursePublishTarget(
        resource({
          title: '图论入门讲义',
          content_text: '后续章节会比较归并排序与其他算法的复杂度。',
        }),
        outline,
      ),
    ).toBeNull()
  })
})
