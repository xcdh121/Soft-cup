import { useSearch } from '@tanstack/react-router'
import { LogIn } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/use-auth'

export const LoginButton = () => {
  const { login, isLoading, loginError } = useAuth()
  const search = useSearch({ from: '/' })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  const handleLogin = (event: React.FormEvent) => {
    event.preventDefault()
    if (search?.redirect) {
      sessionStorage.setItem('auth.redirect', search.redirect)
    }
    login({ username, password })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="flex items-center gap-2">
          <LogIn className="h-4 w-4" />
          登录
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登录</DialogTitle>
          <DialogDescription>使用账户名和密码登录。</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="login-username">账户名</Label>
            <Input
              id="login-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoComplete="username"
              placeholder="请输入账户名"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="login-password">密码</Label>
            <Input
              id="login-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              placeholder="请输入密码"
            />
          </div>
          {loginError && (
            <p className="text-sm text-red-500">
              {loginError instanceof Error ? loginError.message : '登录失败'}
            </p>
          )}
          <Button type="submit" disabled={isLoading || !username || !password}>
            {isLoading ? '正在登录...' : '登录'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
