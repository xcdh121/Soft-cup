import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export const SignUpPage = () => {
  const { signUp, isLoading, signUpError, isAuthenticated, user } = useAuth()
  const navigate = useNavigate()
  const search = useSearch({ from: '/sign-up' })
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated) return
    if (user?.is_admin) {
      sessionStorage.removeItem('auth.redirect')
      void navigate({ to: '/admin', replace: true })
      return
    }
    const redirectUrl =
      search?.redirect || sessionStorage.getItem('auth.redirect')
    sessionStorage.removeItem('auth.redirect')
    void navigate({
      to: redirectUrl?.startsWith('/dashboard') ? redirectUrl : '/dashboard',
      replace: true,
    })
  }, [isAuthenticated, navigate, search?.redirect, user?.is_admin])

  useEffect(() => {
    if (signUpError) {
      setError(
        signUpError instanceof Error ? signUpError.message : '注册失败，请重试',
      )
    }
  }, [signUpError])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    if (password.length < 8) {
      setError('密码至少需要 8 个字符')
      return
    }
    if (search?.redirect) {
      sessionStorage.setItem('auth.redirect', search.redirect)
    }
    signUp({ username, password, name: name || undefined })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md space-y-8 rounded-3xl border border-border/90 bg-card p-8 shadow-xl sm:p-10">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">创建账号</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            账号信息将安全保存在平台自己的数据库中
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name">姓名（可选）</Label>
            <Input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              maxLength={100}
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="username">账户名</Label>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              minLength={3}
              maxLength={50}
              autoComplete="username"
              placeholder="至少 3 个字符"
              disabled={isLoading}
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
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              placeholder="至少 8 个字符"
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">确认密码</Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              autoComplete="new-password"
              disabled={isLoading}
            />
          </div>
          {error && (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 p-3">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={isLoading || !username || !password || !confirmPassword}
          >
            {isLoading ? '正在创建账号...' : '创建账号'}
          </Button>
          <div className="text-center text-sm text-muted-foreground">
            已有账号？{' '}
            <Link
              to="/sign-in"
              search={
                search?.redirect ? { redirect: search.redirect } : undefined
              }
              className="text-primary hover:underline"
            >
              登录
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
