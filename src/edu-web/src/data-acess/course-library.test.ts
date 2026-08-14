// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'

describe('course library request lifecycle', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('does not request authenticated courses when mounted without a session', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const [{ Registry }, { coursesAtom }] = await Promise.all([
      import('@effect-atom/atom-react'),
      import('./course-library'),
    ])
    const registry = Registry.make()
    const unmount = registry.mount(coursesAtom)
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(fetchMock).not.toHaveBeenCalled()

    unmount()
    registry.dispose()
  })
})
