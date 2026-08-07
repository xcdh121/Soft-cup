import { Effect } from 'effect'
import { env } from '@/env'

export type AuthUser = {
  id: string
  username: string
  name: string | null
  avatar_url: string | null
  is_active: boolean
  is_admin: boolean
}

export type AuthSession = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

type AuthResponse = AuthSession
type AuthEvent = 'INITIAL_SESSION' | 'SIGNED_IN' | 'SIGNED_OUT'
type AuthListener = (event: AuthEvent, session: AuthSession | null) => void
type ValidationIssue = { loc?: Array<string | number>; msg?: string }

const storageKey = 'edu-agent.auth.session'
const listeners = new Set<AuthListener>()
const baseUrl = env.VITE_SERVER_URL ?? window.location.origin

const decodeExpiry = (token: string): number | null => {
  try {
    const segment = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = segment.padEnd(
      segment.length + ((4 - (segment.length % 4)) % 4),
      '=',
    )
    const payload = JSON.parse(atob(padded))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

const readSession = (): AuthSession | null => {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return null
  try {
    const session = JSON.parse(raw) as AuthSession
    const expiresAt = decodeExpiry(session.access_token)
    if (!expiresAt || expiresAt <= Date.now()) {
      localStorage.removeItem(storageKey)
      return null
    }
    return session
  } catch {
    localStorage.removeItem(storageKey)
    return null
  }
}

const publish = (event: AuthEvent, session: AuthSession | null) => {
  if (session) localStorage.setItem(storageKey, JSON.stringify(session))
  else localStorage.removeItem(storageKey)
  listeners.forEach((listener) => listener(event, session))
}

const getErrorMessage = (payload: unknown, status: number): string => {
  if (!payload || typeof payload !== 'object') {
    return `认证请求失败（${status}）`
  }
  const responseError = (payload as { error?: unknown }).error
  if (responseError && typeof responseError === 'object') {
    const message = (responseError as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: ValidationIssue) => {
        const field = item.loc?.at(-1)
        return item.msg ? `${field ? `${field}：` : ''}${item.msg}` : null
      })
      .filter(Boolean)
    if (messages.length) return messages.join('；')
  }
  return `认证请求失败（${status}）`
}

const post = async (path: string, body: object): Promise<AuthResponse> => {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = (await response.json().catch(() => null)) as unknown
  if (!response.ok) {
    throw new Error(getErrorMessage(payload, response.status))
  }
  return payload as AuthResponse
}

const authorizedRequest = async <T>(
  path: string,
  init: RequestInit,
): Promise<T> => {
  const session = readSession()
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(session
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
      ...init.headers,
    },
  })
  const payload = (await response.json().catch(() => null)) as unknown
  if (!response.ok) {
    throw new Error(getErrorMessage(payload, response.status))
  }
  return payload as T
}

export const profileClient = {
  updateName: (name: string) =>
    authorizedRequest<AuthUser>('/api/v1/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  uploadAvatar: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return authorizedRequest<AuthUser>('/api/v1/auth/me/avatar', {
      method: 'POST',
      body,
    })
  },
}

export const resolveAvatarUrl = (url: string | null | undefined) => {
  if (!url) return undefined
  return new URL(url, `${baseUrl}/`).toString()
}

export const authClient = {
  auth: {
    getSession: () =>
      Promise.resolve({
        data: { session: readSession() },
        error: null,
      }),
    onAuthStateChange: (listener: AuthListener) => {
      listeners.add(listener)
      queueMicrotask(() => listener('INITIAL_SESSION', readSession()))
      return {
        data: {
          subscription: {
            unsubscribe: () => listeners.delete(listener),
          },
        },
      }
    },
    signInWithPassword: async ({
      username,
      password,
    }: {
      username: string
      password: string
    }) => {
      try {
        const session = await post('/api/v1/auth/login', { username, password })
        publish('SIGNED_IN', session)
        return { data: { session, user: session.user }, error: null }
      } catch (error) {
        return { data: { session: null, user: null }, error: error as Error }
      }
    },
    signUp: async ({
      username,
      password,
      name,
    }: {
      username: string
      password: string
      name?: string
    }) => {
      try {
        const session = await post('/api/v1/auth/register', {
          username,
          password,
          name,
        })
        publish('SIGNED_IN', session)
        return { data: { session, user: session.user }, error: null }
      } catch (error) {
        return { data: { session: null, user: null }, error: error as Error }
      }
    },
    signOut: () => {
      publish('SIGNED_OUT', null)
      return Promise.resolve({ error: null })
    },
  },
}

export const getAccessTokenEffect = Effect.promise(async () => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  return session?.access_token ?? null
})
