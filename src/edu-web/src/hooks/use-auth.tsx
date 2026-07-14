import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAtomValue } from '@effect-atom/atom-react'
import { authClient } from '@/lib/auth-client'
import { authAtom } from '@/data-acess/auth'

export const useAuth = () => {
  const { session, user } = useAtomValue(authAtom)
  const queryClient = useQueryClient()

  const loginMutation = useMutation({
    mutationFn: async (payload: { username: string; password: string }) => {
      const { data, error } = await authClient.auth.signInWithPassword(payload)
      if (error) throw error
      return data
    },
    onError: (error) => console.error('Login failed:', error),
  })

  const signUpMutation = useMutation({
    mutationFn: async (payload: {
      username: string
      password: string
      name?: string
    }) => {
      const { data, error } = await authClient.auth.signUp(payload)
      if (error) throw error
      return data
    },
    onError: (error) => console.error('Sign up failed:', error),
  })

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await authClient.auth.signOut()
    },
    onSuccess: () => queryClient.clear(),
    onError: (error) => console.error('Logout failed:', error),
  })

  return {
    isAuthenticated: !!session && !!user,
    session,
    user,
    login: loginMutation.mutate,
    signUp: signUpMutation.mutate,
    logout: logoutMutation.mutate,
    getAccessToken: () => session?.access_token ?? null,
    isLoading:
      loginMutation.isPending ||
      logoutMutation.isPending ||
      signUpMutation.isPending,
    loginError: loginMutation.error,
    logoutError: logoutMutation.error,
    signUpError: signUpMutation.error,
  }
}
