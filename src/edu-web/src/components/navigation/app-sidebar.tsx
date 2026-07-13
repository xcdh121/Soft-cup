import {
  BookOpen,
  BrainCircuitIcon,
  BrainIcon,
  LibraryBigIcon,
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
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <BrainIcon className="size-4" />
                </div>
                <span className="text-lg font-bold">EduAgent</span>
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
              title: '课程资料库',
              url: '/dashboard/course-library',
              icon: LibraryBigIcon,
            },
            {
              title: '智能协作观测台',
              url: '/dashboard/agent-runtime',
              icon: BrainCircuitIcon,
            },
            {
              title: 'Docs',
              url: 'https://github.com/StudentTraineeCenter/edu-agent/tree/master/docs',
              icon: BookOpen,
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
