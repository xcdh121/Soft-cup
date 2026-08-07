import { Atom, Registry } from '@effect-atom/atom-react'
import { Effect } from 'effect'
import type { AuthSession, AuthUser } from '@/lib/auth-client'
import { ApiClientService } from '@/integrations/api/http'
import { authClient, profileClient } from '@/lib/auth-client'

export const currentUserAtom = Atom.make(
  Effect.gen(function* () {
    const { apiClient } = yield* ApiClientService
    const resp = yield* apiClient.getCurrentUserInfoApiV1AuthMeGet()
    const name = resp.name?.trim() || resp.username
    const initials = name
      .split(' ')
      .map((part: string) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
    return { ...resp, name, initials }
  }).pipe(Effect.provide(ApiClientService.Default)),
)

export const authAtom: Atom.Atom<{
  session: AuthSession | null
  user: AuthUser | null
}> = Atom.make((get) => {
  authClient.auth.getSession().then(({ data: { session } }) => {
    get.setSelf({ session, user: session?.user ?? null })
  })
  const {
    data: { subscription },
  } = authClient.auth.onAuthStateChange((_event, session) => {
    get.setSelf({ session, user: session?.user ?? null })
  })
  get.addFinalizer(() => subscription.unsubscribe())
  return { session: null, user: null }
})

export const isAuthenticatedAtom = Atom.make((get) => {
  const auth = get(authAtom)
  return !!auth.session && !!auth.user
})

export const signInAtom = Atom.fn(
  Effect.fn(function* (payload: { username: string; password: string }) {
    yield* Effect.promise(async () => {
      const { data, error } = await authClient.auth.signInWithPassword(payload)
      if (error) throw error
      return data
    })
  }),
)

export const signUpAtom = Atom.fn(
  Effect.fn(function* (payload: {
    username: string
    password: string
    name?: string
  }) {
    yield* Effect.promise(async () => {
      const { data, error } = await authClient.auth.signUp(payload)
      if (error) throw error
      return data
    })
  }),
)

export const signOutAtom = Atom.fn(
  Effect.fn(function* () {
    yield* Effect.promise(async () => {
      await authClient.auth.signOut()
    })
  }),
)

export const updateCurrentUserNameAtom = Atom.fn(
  Effect.fn(function* (name: string) {
    const registry = yield* Registry.AtomRegistry
    const user = yield* Effect.tryPromise(() => profileClient.updateName(name))
    registry.refresh(currentUserAtom)
    return user
  }),
)

export const uploadCurrentUserAvatarAtom = Atom.fn(
  Effect.fn(function* (file: File) {
    const registry = yield* Registry.AtomRegistry
    const user = yield* Effect.tryPromise(() => profileClient.uploadAvatar(file))
    registry.refresh(currentUserAtom)
    return user
  }),
)
