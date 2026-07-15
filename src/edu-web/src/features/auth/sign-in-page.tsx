import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { useAtom, useAtomValue } from '@effect-atom/atom-react'
import { Cause } from 'effect'
import brandLogo from '../../../../source/4.jpg'
import loginBackground from '../../../../source/7.jpg'
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
    <main className="relative min-h-svh overflow-hidden bg-[#d9eef2]">
      <img
        src={loginBackground}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center"
      />
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(235,249,244,0.05)_0%,rgba(223,242,247,0.04)_48%,rgba(246,250,252,0.5)_64%,rgba(246,250,252,0.82)_100%)]" />

      <section className="relative ml-auto flex min-h-svh w-full items-center justify-center px-5 py-8 sm:px-10 lg:w-1/2 lg:px-12">
        <div className="w-full max-w-[470px] rounded-[32px] border border-white/80 bg-white/96 px-8 py-10 shadow-[0_28px_80px_rgba(30,64,78,0.14)] backdrop-blur-md sm:min-h-[620px] sm:px-12 sm:py-11">
          <div className="flex items-start justify-between gap-5">
            <div>
              <div
                className="h-[68px] w-40 overflow-hidden"
                aria-label="万径"
              >
                <img
                  src={brandLogo}
                  alt="万径"
                  className="-mt-[45px] size-40 max-w-none object-cover"
                />
              </div>
              <p className="mt-1 text-sm font-medium text-slate-700">
                欢迎来到 <span className="text-[#168c91]">万径</span>
              </p>
            </div>
            <p className="pt-2 text-right text-xs leading-5 text-slate-400">
              还没有账号？
              <br />
              <Link
                to="/sign-up"
                search={
                  search?.redirect ? { redirect: search.redirect } : undefined
                }
                className="font-medium text-[#168c91] transition-colors hover:text-[#0f6f75] hover:underline"
              >
                立即注册
              </Link>
            </p>
          </div>

          <div className="mt-7">
            <h1 className="text-center text-[28px] font-semibold leading-none tracking-[-0.02em] text-slate-950">
              登录
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-7">
            <div className="space-y-2.5">
              <Label
                htmlFor="username"
                className="text-sm font-medium text-slate-800"
              >
                账户名
              </Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                autoFocus
                autoComplete="username"
                placeholder="请输入账户名"
                disabled={signInResult.waiting}
                className="h-13 rounded-xl border-slate-200 bg-white px-4 shadow-none placeholder:text-slate-400 focus-visible:border-[#168c91] focus-visible:ring-[#168c91]/15"
              />
            </div>
            <div className="space-y-2.5">
              <Label
                htmlFor="password"
                className="text-sm font-medium text-slate-800"
              >
                密码
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                autoComplete="current-password"
                placeholder="请输入密码"
                disabled={signInResult.waiting}
                className="h-13 rounded-xl border-slate-200 bg-white px-4 shadow-none placeholder:text-slate-400 focus-visible:border-[#168c91] focus-visible:ring-[#168c91]/15"
              />
            </div>
            {signInResult._tag === 'Failure' && (
              <div
                role="alert"
                className="rounded-lg border border-destructive/20 bg-destructive/5 p-3"
              >
                <p className="text-sm text-destructive">
                  登录失败：{Cause.pretty(signInResult.cause)}
                </p>
              </div>
            )}
            <Button
              type="submit"
              className="mt-3 h-13 w-full rounded-xl bg-[#153f68] font-medium shadow-[0_8px_22px_rgba(21,63,104,0.2)] transition-all hover:-translate-y-0.5 hover:bg-[#0f3459] hover:shadow-[0_12px_26px_rgba(21,63,104,0.24)]"
              disabled={signInResult.waiting || !username || !password}
            >
              {signInResult.waiting ? '正在登录...' : '登录'}
            </Button>
          </form>
        </div>
      </section>
    </main>
  )
}
