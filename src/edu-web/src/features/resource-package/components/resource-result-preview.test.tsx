// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResourceResultPreview } from './resource-result-preview'
import type { GeneratedResource } from '@/data-acess/resource-package'

describe('ResourceResultPreview', () => {
  it('uses only the package stream while a note is generating', () => {
    const resource: GeneratedResource = {
      id: 'resource-1',
      resource_package_id: 'package-1',
      project_id: 'project-1',
      user_id: 'user-1',
      resource_type: 'lecture_note',
      title: 'Streaming note',
      summary: null,
      status: 'generating',
      format: 'note-ref',
      content_text: null,
      content_json: {
        target_id: 'note-1',
        target_type: 'note',
      },
      file_url: null,
      preview_url: '/dashboard/p/project-1/n/note-1',
      cover_image_url: null,
      source_document_ids: [],
      knowledge_point_ids: [],
      difficulty_level: 'intermediate',
      estimated_minutes: 25,
      version: 1,
      generation_order: 0,
      generator_agent: 'ResourceAgent',
      generation_reason: null,
      error_message: null,
      created_at: '2026-08-17T00:00:00Z',
      updated_at: '2026-08-17T00:00:00Z',
      completed_at: null,
    }

    render(
      <ResourceResultPreview projectId="project-1" resource={resource} />,
    )

    expect(
      screen.getAllByText(
        '笔记模型正在准备，首段内容生成后会在这里实时显示…',
      ),
    ).toHaveLength(1)
    expect(
      screen.queryByText('笔记正在排队生成，内容完成后会自动显示...'),
    ).toBeNull()
  })

  it('does not report an empty video result while search is still running', () => {
    const resource: GeneratedResource = {
      id: 'resource-video-1',
      resource_package_id: 'package-1',
      project_id: 'project-1',
      user_id: 'user-1',
      resource_type: 'video_recommendations',
      title: 'Generating video recommendations',
      summary: null,
      status: 'generating',
      format: 'json',
      content_text: null,
      content_json: null,
      file_url: null,
      preview_url: null,
      cover_image_url: null,
      source_document_ids: [],
      knowledge_point_ids: [],
      difficulty_level: 'intermediate',
      estimated_minutes: null,
      version: 1,
      generation_order: 3,
      generator_agent: null,
      generation_reason: null,
      error_message: null,
      created_at: '2026-08-17T00:00:00Z',
      updated_at: '2026-08-17T00:00:00Z',
      completed_at: null,
    }

    render(
      <ResourceResultPreview projectId="project-1" resource={resource} />,
    )

    expect(screen.getByText('正在搜索相关视频…')).toBeTruthy()
    expect(screen.queryByText('暂未找到相关视频。')).toBeNull()
  })
})
