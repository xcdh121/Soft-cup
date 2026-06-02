import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export const SignUpPage = () => {
  const { signUp, isLoading, signUpError, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const search = useSearch({ from: '/sign-up' })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [hasSubmitted, setHasSubmitted] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !hasSubmitted) {
      const redirectUrl =
        search?.redirect || sessionStorage.getItem('auth.redirect')
      if (redirectUrl) {
        sessionStorage.removeItem('auth.redirect')
        const dashboardUrl = redirectUrl.startsWith('/dashboard')
          ? redirectUrl
          : `/dashboard${redirectUrl}`
        navigate({ to: dashboardUrl })
      } else {
        navigate({ to: '/dashboard' })
      }
    }
  }, [isAuthenticated, navigate, search?.redirect, hasSubmitted])

  // Update error when signUpError changes
  useEffect(() => {
    if (signUpError) {
      setError(
        signUpError instanceof Error
          ? signUpError.message
          : '注册失败，请重试。',
      )
      setHasSubmitted(false)
    }
  }, [signUpError])

  // Handle successful sign-up (might need email confirmation)
  useEffect(() => {
    if (hasSubmitted && !isLoading && !signUpError) {
      // Sign-up completed successfully
      if (isAuthenticated) {
        // User is authenticated immediately (no email confirmation required)
        const redirectUrl =
          search?.redirect || sessionStorage.getItem('auth.redirect')
        if (redirectUrl) {
          sessionStorage.removeItem('auth.redirect')
          const dashboardUrl = redirectUrl.startsWith('/dashboard')
            ? redirectUrl
            : `/dashboard${redirectUrl}`
          navigate({ to: dashboardUrl })
        } else {
          navigate({ to: '/dashboard' })
        }
      } else {
        // Email confirmation required
        setSuccess(true)
      }
    }
  }, [
    hasSubmitted,
    isLoading,
    signUpError,
    isAuthenticated,
    navigate,
    search?.redirect,
  ])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    setHasSubmitted(false)

    if (!email || !password || !confirmPassword) {
      setError('请填写所有字段')
      return
    }

    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }

    if (password.length < 6) {
      setError('密码长度至少需要 6 个字符')
      return
    }

    // Store the redirect URL before sign up
    if (search?.redirect) {
      sessionStorage.setItem('auth.redirect', search.redirect)
    }

    setHasSubmitted(true)
    signUp({ email, password })
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center space-y-4">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              请检查你的邮箱
            </h1>
            <p className="text-sm text-muted-foreground">
              我们已向 <strong>{email}</strong> 发送确认链接
            </p>
            <p className="text-sm text-muted-foreground">
              请点击邮件中的链接验证账号并完成注册。
            </p>
            <div className="pt-4">
              <Link
                to="/sign-in"
                className="text-sm text-primary hover:underline"
              >
                返回登录
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            创建账号
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            输入邮箱和密码来创建账号
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              autoComplete="email"
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="至少 6 个字符"
              autoComplete="new-password"
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">确认密码</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="请再次输入密码"
              autoComplete="new-password"
              disabled={isLoading}
            />
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={isLoading || !email || !password || !confirmPassword}
          >
            {isLoading ? '正在创建账号...' : '创建账号'}
          </Button>

          <div className="text-center text-xs text-muted-foreground">
            创建账号即表示你同意我们的{' '}
            <a
              href="https://github.com/StudentTraineeCenter/edu-agent/blob/master/docs/PRIVACY_POLICY.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              隐私政策
            </a>
          </div>

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
