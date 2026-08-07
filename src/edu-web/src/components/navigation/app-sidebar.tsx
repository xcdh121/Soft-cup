import {
  BrainCircuitIcon,
  CreditCard,
  GraduationCapIcon,
  Settings2,
} from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { CurrentProjectNav } from './current-project-nav'
import { NavMain } from './nav-main'
import { NavProjects } from './nav-projects'
import { NavUser } from './nav-user'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar
      collapsible="icon"
      className="border-sidebar-border shadow-[2px_0_18px_rgba(31,86,145,0.07)]"
      {...props}
    >
      <SidebarHeader className="border-sidebar-border/80 border-b px-3 py-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground hover:bg-sidebar-accent/80"
              asChild
            >
              <Link to="/dashboard">
                <img
                  src="/source/4.jpg"
                  alt="万径"
                  className="aspect-square size-10 rounded-lg object-cover"
                />
                <span className="text-sidebar-primary text-lg font-semibold tracking-wide">
                  万径
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent className="py-2">
        <NavProjects />
        <CurrentProjectNav />
        <NavMain
          items={[
            {
              title: '我的课程',
              url: '/dashboard/my-courses',
              icon: GraduationCapIcon,
            },
            {
              title: '智能协作观测台',
              url: '/dashboard/agent-runtime',
              icon: BrainCircuitIcon,
            },
            {
              title: '套餐与额度',
              url: '/dashboard/billing',
              icon: CreditCard,
            },
            {
              title: 'Settings',
              url: '/dashboard/settings',
              icon: Settings2,
            },
          ]}
        />
      </SidebarContent>
      <SidebarFooter className="border-sidebar-border/80 border-t px-3 py-3">
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
