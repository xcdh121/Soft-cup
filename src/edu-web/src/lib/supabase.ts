import { env } from '@/env'
import { createClient } from '@supabase/supabase-js'
import { Effect } from 'effect'

export const isSupabaseConfigured = Boolean(
  env.VITE_SUPABASE_URL && env.VITE_SUPABASE_ANON_KEY,
)

const createFallbackClient = () => ({
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({
      data: {
        subscription: {
          unsubscribe: () => undefined,
        },
      },
    }),
    signInWithPassword: async () => ({
      data: { session: null, user: null },
      error: null,
    }),
    signInWithOtp: async () => ({
      data: { session: null, user: null },
      error: null,
    }),
    signUp: async () => ({
      data: { session: null, user: null },
      error: null,
    }),
    signOut: async () => ({ error: null }),
  },
})

export const supabase = isSupabaseConfigured
  ? createClient(env.VITE_SUPABASE_URL!, env.VITE_SUPABASE_ANON_KEY!, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    })
  : createFallbackClient()

export const getAccessTokenEffect = Effect.promise(async () => {
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session?.access_token ?? null
})
