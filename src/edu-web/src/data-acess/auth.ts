import { Atom } from '@effect-atom/atom-react'
import { Effect } from 'effect'
import type { Session, User } from '@supabase/supabase-js'
import { ApiClientService } from '@/integrations/api/http'
import { isSupabaseConfigured, supabase } from '@/lib/supabase'

const authBypassedUser = {
  id: 'local-dev-user',
  email: 'local@dev.test',
  user_metadata: {
    name: 'Local Developer',
  },
} as unknown as User

export const currentUserAtom = Atom.make(
  Effect.gen(function* () {
    if (!isSupabaseConfigured) {
      return {
        ...authBypassedUser,
        name: 'Local Developer',
        initials: 'LD',
      }
    }

    const { apiClient } = yield* ApiClientService
    const resp = yield* apiClient.getCurrentUserInfoApiV1AuthMeGet()

    const name = resp.name?.trim() ?? resp.email?.split('@')[0] ?? 'User'

    const initials = name
      .split(' ')
      .map((n: string) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)

    return {
      ...resp,
      name,
      initials,
    }
  }).pipe(Effect.provide(ApiClientService.Default)),
).pipe(Atom.keepAlive)

export const authAtom: Atom.Atom<{
  session: Session | null
  user: User | null
}> = Atom.make((get) => {
  if (!isSupabaseConfigured) {
    return {
      session: null,
      user: authBypassedUser,
    }
  }

  supabase.auth.getSession().then(({ data: { session } }) => {
    get.setSelf({ session, user: session?.user ?? null })
  })

  const {
    data: { subscription },
  } = supabase.auth.onAuthStateChange((_event, session) => {
    get.setSelf({ session, user: session?.user ?? null })
  })

  get.addFinalizer(() => subscription.unsubscribe())

  return { session: null, user: null }
})

export const isAuthenticatedAtom = Atom.make((get) => {
  if (!isSupabaseConfigured) {
    return true
  }

  const auth = get(authAtom)
  return !!auth.session && !!auth.user
})

type SignInPayload =
  | {
      readonly type: 'password'
      readonly email: string
      readonly password: string
    }
  | { readonly type: 'magic_link'; readonly email: string }

export const signInAtom = Atom.fn(
  Effect.fn(function* (payload: SignInPayload) {
    if (!isSupabaseConfigured) {
      return payload
    }

    if (payload.type === 'password') {
      yield* Effect.promise(async () => {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: payload.email,
          password: payload.password,
        })
        if (error) throw error
        return data
      })
    } else {
      yield* Effect.promise(async () => {
        const { data, error } = await supabase.auth.signInWithOtp({
          email: payload.email,
          options: {
            emailRedirectTo: window.location.origin,
          },
        })
        if (error) throw error
        return data
      })
    }
  }),
)

export const signUpAtom = Atom.fn(
  Effect.fn(function* (payload: { email: string; password: string }) {
    if (!isSupabaseConfigured) {
      return payload
    }

    yield* Effect.promise(async () => {
      const { data, error } = await supabase.auth.signUp({
        email: payload.email,
        password: payload.password,
        options: {
          emailRedirectTo: window.location.origin,
        },
      })
      if (error) throw error
      return data
    })
  }),
)

export const signOutAtom = Atom.fn(
  Effect.fn(function* () {
    if (!isSupabaseConfigured) {
      return
    }

    yield* Effect.promise(async () => {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    })
  }),
)
