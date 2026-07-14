import { Outlet, useLocation } from '@tanstack/react-router'
import { useAtomValue } from '@effect-atom/atom-react'
import { AppSidebar } from '@/components/navigation/app-sidebar'
import { AppBreadcrumbs } from '@/components/navigation/app-breadcrumbs'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { isAuthenticatedAtom } from '@/data-acess/auth'

export const AppShell = () => {
  const isAuthenticated = useAtomValue(isAuthenticatedAtom)

  const location = useLocation()

  // Only show sidebar on dashboard routes
  const isDashboardRoute = location.pathname.startsWith('/dashboard')
  const isDocumentDetailRoute = /^\/dashboard\/p\/[^/]+\/d\/[^/]+/.test(
    location.pathname,
  )

  if (!isAuthenticated || !isDashboardRoute) {
    return <Outlet />
  }

  return (
    <SidebarProvider
      className={isDocumentDetailRoute ? 'h-svh overflow-hidden' : undefined}
    >
      <AppSidebar />
      <SidebarInset className="h-svh min-w-0 overflow-hidden">
        <AppBreadcrumbs />
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
  )
}
