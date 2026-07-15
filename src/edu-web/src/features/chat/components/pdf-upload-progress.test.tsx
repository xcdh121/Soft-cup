// @vitest-environment jsdom

import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PdfUploadProgress } from './pdf-upload-progress'

describe('PdfUploadProgress', () => {
  it('shows the current document stage and percentage', () => {
    const { container } = render(
      <PdfUploadProgress
        value={{
          fileName: '课程讲义.pdf',
          label: '正在识别文档',
          detail: '正在提取文字、公式与版面结构',
          progress: 65,
          state: 'active',
        }}
      />,
    )

    expect(container.textContent).toContain('正在识别文档')
    expect(container.textContent).toContain('课程讲义.pdf')
    expect(container.textContent).toContain('65%')
    expect(
      container.querySelector('[aria-label="PDF 处理进度 65%"]'),
    ).not.toBeNull()
  })

  it('keeps the failure reason visible', () => {
    const { container } = render(
      <PdfUploadProgress
        value={{
          fileName: '扫描件.pdf',
          label: '文档处理失败',
          detail: '识别结果读取失败',
          progress: 78,
          state: 'error',
        }}
      />,
    )

    expect(container.textContent).toContain('文档处理失败')
    expect(container.textContent).toContain('识别结果读取失败')
  })
})
