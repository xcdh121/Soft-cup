import { BrainCircuitIcon, GraduationCapIcon, Settings2 } from 'lucide-react'
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
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              asChild
            >
              <Link to="/dashboard">
                <img
                  src="/source/4.jpg"
                  alt="万径"
                  className="aspect-square size-10 rounded-lg object-cover"
                />
                <span className="text-lg font-bold">万径</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
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
              title: 'Settings',
              url: '/dashboard/settings',
              icon: Settings2,
            },
          ]}
        />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
