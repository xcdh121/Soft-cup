import { useAtomValue } from '@effect-atom/atom-react'
import { Outlet, useLocation, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { AppSidebar } from '@/components/navigation/app-sidebar'
import { Button } from '@/components/ui/button'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { isAuthenticatedAtom } from '@/data-acess/auth'
import { DigitalAvatarPanel } from '@/features/chat/components/digital-avatar-panel'
import { authClient } from '@/lib/auth-client'

type ProjectAccessStatus = 'checking' | 'allowed' | 'missing' | 'error'

const ProjectRouteGuard = ({
  projectId,
  children,
}: {
  projectId: string
  children: ReactNode
}) => {
  const navigate = useNavigate()
  const [status, setStatus] = useState<ProjectAccessStatus>('checking')
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    setStatus('checking')
    void (async () => {
      const {
        data: { session },
      } = await authClient.auth.getSession()
      if (!session) {
        setStatus('error')
        return
      }

      const baseUrl = import.meta.env.VITE_SERVER_URL ?? 'http://localhost:8000'
      const response = await fetch(
        `${baseUrl}/api/v1/projects/${encodeURIComponent(projectId)}`,
        {
          headers: { Authorization: `Bearer ${session.access_token}` },
          signal: controller.signal,
        },
      )
      if (controller.signal.aborted) return

      if (response.status === 404) {
        setStatus('missing')
        await navigate({ to: '/dashboard', replace: true })
        return
      }
      setStatus(response.ok ? 'allowed' : 'error')
    })().catch((error: unknown) => {
      if (
        !controller.signal.aborted &&
        !(error instanceof DOMException && error.name === 'AbortError')
      ) {
        setStatus('error')
      }
    })

    return () => {
      controller.abort()
    }
  }, [navigate, projectId, retryCount])

  if (status === 'allowed') return children

  if (status === 'error') {
    return (
      <div className="flex h-svh flex-col items-center justify-center gap-3 px-4 text-center">
        <p className="text-sm text-destructive">无法验证项目访问权限</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setRetryCount((n) => n + 1)}>
            重试
          </Button>
          <Button onClick={() => navigate({ to: '/dashboard', replace: true })}>
            返回项目列表
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-svh items-center justify-center text-sm text-muted-foreground">
      {status === 'missing' ? '项目不可访问，正在返回项目列表...' : '正在验证项目...'}
    </div>
  )
}

const DashboardShell = ({
  isDocumentDetailRoute,
}: {
  isDocumentDetailRoute: boolean
}) => (
  <>
    <SidebarProvider
      className={isDocumentDetailRoute ? 'h-svh overflow-hidden' : undefined}
    >
      <AppSidebar />
      <SidebarInset className="h-svh min-w-0 overflow-hidden bg-[#fbfcfe] dark:bg-background">
        <div
          className={
            isDocumentDetailRoute
              ? 'min-h-0 flex-1 overflow-hidden'
              : 'min-h-0 flex-1 overflow-auto'
          }
        >
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
    <DigitalAvatarPanel />
  </>
)

export const AppShell = () => {
  const isAuthenticated = useAtomValue(isAuthenticatedAtom)

  const location = useLocation()

  // Only show sidebar on dashboard routes
  const isDashboardRoute = location.pathname.startsWith('/dashboard')
  const isDocumentDetailRoute = /^\/dashboard\/p\/[^/]+\/d\/[^/]+/.test(
    location.pathname,
  )
  const projectId = location.pathname.match(/^\/dashboard\/p\/([^/]+)/)?.[1]

  if (!isAuthenticated || !isDashboardRoute) {
    return (
      <>
        <Outlet />
        <DigitalAvatarPanel />
      </>
    )
  }

  const dashboardShell = (
    <DashboardShell isDocumentDetailRoute={isDocumentDetailRoute} />
  )

  return projectId ? (
    <ProjectRouteGuard projectId={decodeURIComponent(projectId)}>
      {dashboardShell}
    </ProjectRouteGuard>
  ) : (
    dashboardShell
  )
}
