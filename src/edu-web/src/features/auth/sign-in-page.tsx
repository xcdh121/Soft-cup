import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { useAtom, useAtomValue } from '@effect-atom/atom-react'
import { Cause } from 'effect'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { isAuthenticatedAtom, signInAtom } from '@/data-acess/auth'

export const SignInPage = () => {
  const [signInResult, signIn] = useAtom(signInAtom)
  const isAuthenticated = useAtomValue(isAuthenticatedAtom)
  const navigate = useNavigate()
  const search = useSearch({ from: '/sign-in' })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return
    const redirectUrl =
      search?.redirect || sessionStorage.getItem('auth.redirect')
    sessionStorage.removeItem('auth.redirect')
    navigate({
      to: redirectUrl
        ? redirectUrl.startsWith('/dashboard')
          ? redirectUrl
          : `/dashboard${redirectUrl}`
        : '/dashboard',
    })
  }, [isAuthenticated, navigate, search?.redirect])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (search?.redirect) {
      sessionStorage.setItem('auth.redirect', search.redirect)
    }
    signIn({ username, password })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">登录</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            使用你的账户名和密码进入学习平台
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="username">账户名</Label>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoComplete="username"
              placeholder="请输入账户名"
              disabled={signInResult.waiting}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              placeholder="请输入密码"
              disabled={signInResult.waiting}
            />
          </div>
          {signInResult._tag === 'Failure' && (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 p-3">
              <p className="text-sm text-destructive">
                登录失败：{Cause.pretty(signInResult.cause)}
              </p>
            </div>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={signInResult.waiting || !username || !password}
          >
            {signInResult.waiting ? '正在登录...' : '登录'}
          </Button>
          <div className="text-center text-sm text-muted-foreground">
            还没有账号？{' '}
            <Link
              to="/sign-up"
              search={
                search?.redirect ? { redirect: search.redirect } : undefined
              }
              className="text-primary hover:underline"
            >
              注册
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
