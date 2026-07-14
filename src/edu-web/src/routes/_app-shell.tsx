import { Outlet, useLocation } from '@tanstack/react-router'
import { useAtomValue } from '@effect-atom/atom-react'
import { AppSidebar } from '@/components/navigation/app-sidebar'
import { AppBreadcrumbs } from '@/components/navigation/app-breadcrumbs'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { isAuthenticatedAtom } from '@/data-acess/auth'
import { DigitalAvatarPanel } from '@/features/chat/components/digital-avatar-panel'

export const AppShell = () => {
  const isAuthenticated = useAtomValue(isAuthenticatedAtom)

  const location = useLocation()

  // Only show sidebar on dashboard routes
  const isDashboardRoute = location.pathname.startsWith('/dashboard')
  const isDocumentDetailRoute = /^\/dashboard\/p\/[^/]+\/d\/[^/]+/.test(
    location.pathname,
  )

  if (!isAuthenticated || !isDashboardRoute) {
    return (
      <>
        <Outlet />
        <DigitalAvatarPanel />
      </>
    )
  }

  return (
    <>
      <SidebarProvider
        className={isDocumentDetailRoute ? 'h-svh overflow-hidden' : undefined}
      >
        <AppSidebar />
        <SidebarInset className="h-svh min-w-0 overflow-hidden bg-[#fbfcfe] dark:bg-background">
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
      <DigitalAvatarPanel />
    </>
  )
}
