import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import type { ProjectDto } from '@/integrations/api/client'
import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { Cause } from 'effect'
import { FolderIcon, PlusIcon } from 'lucide-react'

export function NavProjects() {
  const projectsResult = useAtomValue(projectsAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const renderProjects = () => {
    if (projectsResult.waiting) {
      return (
        <SidebarMenuItem>
          <SidebarMenuButton disabled>
            <span className="text-sm text-muted-foreground">
              Loading projects...
            </span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      )
    }

    if (Result.isFailure(projectsResult)) {
      return (
        <SidebarMenuItem>
          <SidebarMenuButton disabled>
            <span className="text-sm text-muted-foreground">
              Failed to load projects: {Cause.pretty(projectsResult.cause)}
            </span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      )
    }

    if (!Result.isSuccess(projectsResult)) {
      return null
    }

    const projects: readonly ProjectDto[] = projectsResult.value

    if (projects.length === 0) {
      return (
        <SidebarMenuItem>
          <SidebarMenuButton disabled>
            <span className="text-sm text-muted-foreground">
              No projects yet.
            </span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      )
    }

    return (
      <>
        {projects.map((project: ProjectDto) => (
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
    )
  }

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
        {renderProjects()}
      </SidebarMenu>
    </SidebarGroup>
  )
}

export default NavProjects
