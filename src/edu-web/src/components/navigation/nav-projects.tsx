import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { Cause } from 'effect'
import { FolderIcon, PlusIcon } from 'lucide-react'

export function NavProjects() {
  const projectsResult = useAtomValue(projectsAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Projects</SidebarGroupLabel>
      <SidebarMenu>
        <SidebarMenuButton
          tooltip="Create project"
          onClick={() => openCreateProjectDialog()}
        >
          <PlusIcon className="size-4 opacity-70" />
          <span>Create project</span>
        </SidebarMenuButton>

        {Result.builder(projectsResult)
          .onInitialOrWaiting(() => (
            <SidebarMenuItem>
              <SidebarMenuButton disabled>
                <span className="text-sm text-muted-foreground">
                  Loading projects...
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))
          .onFailure((cause) => (
            <SidebarMenuItem>
              <SidebarMenuButton disabled>
                <span className="text-sm text-muted-foreground">
                  Failed to load projects: {Cause.pretty(cause)}
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))
          .onSuccess((projects) => (
            <>
              {projects.length === 0 && (
                <SidebarMenuItem>
                  <SidebarMenuButton disabled>
                    <span className="text-sm text-muted-foreground">
                      No projects yet.
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}

              {projects.map((project) => (
                <SidebarMenuItem key={project.id}>
                  <SidebarMenuButton asChild>
                    <Link
                      to="/dashboard/p/$projectId"
                      params={{ projectId: project.id }}
                    >
                      <FolderIcon className="size-4 opacity-70" />
                      <span>{project.name}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </>
          ))
          .render()}
      </SidebarMenu>
    </SidebarGroup>
  )
}

export default NavProjects
