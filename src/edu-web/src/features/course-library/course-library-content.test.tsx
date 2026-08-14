// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LearningResourceCard } from './course-library-page'
import type { CourseResource } from '@/data-acess/course-library'
import type { GeneratedResource } from '@/data-acess/resource-package'

const generatedResource: GeneratedResource = {
  id: 'generated-1',
  resource_package_id: 'package-1',
  project_id: 'project-1',
  user_id: 'user-1',
  resource_type: 'lecture_note',
  title: '归并排序完整讲义',
  summary: '从分治到合并的系统讲解',
  status: 'completed',
  format: 'markdown',
  content_text: `# 完整正文\n\n${'课程内容'.repeat(400)}\n\n课程正文结尾标记`,
  content_json: null,
  file_url: null,
  preview_url: '/dashboard/p/project-1/resource-packages',
  cover_image_url: null,
  source_document_ids: [],
  knowledge_point_ids: ['point-1'],
  difficulty_level: 'intermediate',
  estimated_minutes: 20,
  version: 1,
  generation_order: 1,
  generator_agent: 'content-agent',
  generation_reason: null,
  error_message: null,
  created_at: '',
  updated_at: '',
  completed_at: '',
}

const courseResource: CourseResource = {
  id: 'course-resource-1',
  course_id: 'course-1',
  chapter_id: 'chapter-1',
  document_id: null,
  document_project_id: null,
  generated_resource_id: generatedResource.id,
  generated_resource: generatedResource,
  resource_type: 'lecture_note',
  title: generatedResource.title,
  description: generatedResource.summary,
  source_type: 'generated',
  source_url: null,
  difficulty_level: 'intermediate',
  estimated_minutes: 20,
  license_info: null,
  target_audiences: ['intermediate'],
  metadata: {},
  knowledge_point_ids: ['point-1'],
  created_at: '',
  updated_at: '',
}

describe('LearningResourceCard', () => {
  it('renders the full generated learning content inside the course card', () => {
    render(<LearningResourceCard resource={courseResource} />)

    expect(screen.getByText('归并排序完整讲义')).toBeTruthy()
    expect(screen.getByText(/课程正文结尾标记/)).toBeTruthy()
    expect(screen.queryByText('打开生成资源')).toBeNull()
  })
})
