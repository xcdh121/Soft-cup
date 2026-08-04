// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CourseCreateDialog } from './course-create-dialog'

const mocks = vi.hoisted(() => ({
  createCourse: vi.fn(),
  uploadCourseCover: vi.fn(),
}))

vi.mock('@/data-acess/billing-admin', () => ({
  adminApi: {
    createCourse: mocks.createCourse,
    uploadCourseCover: mocks.uploadCourseCover,
  },
}))

describe('CourseCreateDialog', () => {
  beforeEach(() => {
    mocks.createCourse.mockReset()
    mocks.createCourse.mockResolvedValue({})
    mocks.uploadCourseCover.mockReset()
    mocks.uploadCourseCover.mockResolvedValue({
      url: '/api/v1/course-covers/cover.png',
    })
  })

  afterEach(() => cleanup())

  it('uses the same visible fields as the learner course card', () => {
    render(
      <CourseCreateDialog open onOpenChange={vi.fn()} onCreated={vi.fn()} />,
    )

    expect(screen.getByLabelText(/课程封面/)).toBeTruthy()
    expect(screen.getByLabelText('课程状态')).toBeTruthy()
    expect(screen.getByLabelText('课程代码')).toBeTruthy()
    expect(screen.getByLabelText(/课程名称/)).toBeTruthy()
    expect(screen.getByLabelText(/一句话简介/)).toBeTruthy()
    expect(screen.queryByText('学生端卡片预览')).toBeNull()
  })

  it('submits the cover and learner-card content', async () => {
    const onCreated = vi.fn()
    const onOpenChange = vi.fn()
    render(
      <CourseCreateDialog
        open
        onOpenChange={onOpenChange}
        onCreated={onCreated}
      />,
    )

    const cover = new File(['cover'], 'course.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText(/课程封面/), {
      target: { files: [cover] },
    })
    fireEvent.change(screen.getByLabelText('课程代码'), {
      target: { value: 'DSA-101' },
    })
    fireEvent.change(screen.getByLabelText(/课程名称/), {
      target: { value: '数据结构与算法' },
    })
    fireEvent.change(screen.getByLabelText(/一句话简介/), {
      target: { value: '从核心结构到经典算法，建立系统化解题能力。' },
    })
    const submitButton = screen.getByRole('button', { name: '创建课程草稿' })
    fireEvent.submit(submitButton.closest('form')!)

    await waitFor(() => {
      expect(mocks.uploadCourseCover).toHaveBeenCalledWith(cover)
      expect(mocks.createCourse).toHaveBeenCalledWith({
        cover_url: '/api/v1/course-covers/cover.png',
        status: 'active',
        code: 'DSA-101',
        name: '数据结构与算法',
        description: '从核心结构到经典算法，建立系统化解题能力。',
      })
    })
    expect(onCreated).toHaveBeenCalledOnce()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
