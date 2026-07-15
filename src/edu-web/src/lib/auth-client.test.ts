import { afterEach, describe, expect, it, vi } from 'vitest'
import { authClient } from './auth-client'

describe('authClient errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders FastAPI validation details instead of object strings', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              { loc: ['body', 'username'], msg: 'Field required' },
              { loc: ['body', 'password'], msg: 'Too short' },
            ],
          }),
          { status: 422, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    const result = await authClient.auth.signInWithPassword({
      username: 'student',
      password: 'secret',
    })

    expect(result.error?.message).toBe(
      'username：Field required；password：Too short',
    )
    expect(result.error?.message).not.toContain('[object Object]')
  })

  it('renders the API custom error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              message: 'AUTH_JWT_SECRET 配置无效',
              status_code: 500,
            },
          }),
          { status: 500, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    const result = await authClient.auth.signInWithPassword({
      username: 'student',
      password: 'secret',
    })

    expect(result.error?.message).toBe('AUTH_JWT_SECRET 配置无效')
  })
})
