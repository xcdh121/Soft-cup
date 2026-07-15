import { Link } from '@tanstack/react-router'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { LogoutButton } from '@/components/auth/logout-button'
import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'
import { currentUserAtom } from '@/data-acess/auth'

export const UserProfile = () => {
  const currentUserResult = useAtomValue(currentUserAtom)

  return Result.builder(currentUserResult)
    .onSuccess(({ name, username, initials }) => (
      <div className="flex items-center gap-3 p-3 border rounded-lg">
        <pre>{JSON.stringify(currentUserResult, null, 2)}</pre>
        <Avatar>
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{name}</p>
          <p className="text-xs text-gray-500 truncate">@{username}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/dashboard"
            className={cn(buttonVariants({ variant: 'default' }))}
          >
            仪表盘
          </Link>
        </div>
        <LogoutButton />
      </div>
    ))
    .onError(() => (
      <div className="flex items-center gap-3 p-3 border rounded-lg">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">用户</p>
          <p className="text-xs text-gray-500 truncate">未登录</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/dashboard"
            className={cn(buttonVariants({ variant: 'default' }))}
          >
            仪表盘
          </Link>
        </div>
        <LogoutButton />
      </div>
    ))
    .orNull()
}
