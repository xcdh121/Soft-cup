import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  BookOpenIcon,
  ChevronRightIcon,
  FolderIcon,
  PlusIcon,
} from 'lucide-react'
import { useMemo } from 'react'
import type { Course } from '@/data-acess/course-library'
import type { ProjectDto } from '@/integrations/api/client'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar'
import { coursesAtom } from '@/data-acess/course-library'
import { projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'

type ProjectGroup = {
  id: string
  name: string
  code?: string | null
  projects: Array<ProjectDto>
}

const unassignedCourseGroup: Omit<ProjectGroup, 'projects'> = {
  id: 'unassigned',
  name: '未关联课程',
  code: null,
}

const buildProjectGroups = (
  courses: ReadonlyArray<Course>,
  projects: ReadonlyArray<ProjectDto>,
) => {
  const courseById = new Map(courses.map((course) => [course.id, course]))
  const groups = new Map<string, ProjectGroup>()

  for (const course of courses) {
    groups.set(course.id, {
      id: course.id,
      name: course.name,
      code: course.code,
      projects: [],
    })
  }

  for (const project of projects) {
    const course = project.course_id
      ? courseById.get(project.course_id)
      : undefined
    const groupId = course?.id ?? unassignedCourseGroup.id
    const group =
      groups.get(groupId) ??
      {
        ...unassignedCourseGroup,
        projects: [],
      }

    group.projects.push(project)
    groups.set(groupId, group)
  }

  return [...groups.values()].sort((left, right) => {
    if (left.id === unassignedCourseGroup.id) return 1
    if (right.id === unassignedCourseGroup.id) return -1
    return left.name.localeCompare(right.name, 'zh-CN')
  })
}

const CourseProjectGroup = ({ group }: { group: ProjectGroup }) => {
  return (
    <Collapsible defaultOpen className="group/course-project">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={group.name}>
            <BookOpenIcon className="size-4 opacity-70" />
            <span className="truncate">{group.name}</span>
            {group.code ? (
              <span className="ml-auto text-xs text-muted-foreground">
                {group.code}
              </span>
            ) : null}
            <ChevronRightIcon className="ml-1 size-4 transition-transform duration-200 group-data-[state=open]/course-project:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {group.projects.length === 0 ? (
              <SidebarMenuSubItem>
                <SidebarMenuSubButton size="md">
                  <span className="text-sm text-muted-foreground">
                    暂无项目
                  </span>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ) : (
              group.projects.map((project) => (
                <SidebarMenuSubItem key={project.id}>
                  <SidebarMenuSubButton asChild size="md">
                    <Link
                      to="/dashboard/p/$projectId"
                      params={{ projectId: project.id }}
                    >
                      <FolderIcon className="size-4 opacity-70" />
                      <span>{project.name}</span>
                    </Link>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              ))
            )}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

export function NavProjects() {
  const coursesResult = useAtomValue(coursesAtom)
  const projectsResult = useAtomValue(projectsAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const courses = Result.isSuccess(coursesResult) ? coursesResult.value : []
  const projects = Result.isSuccess(projectsResult) ? projectsResult.value : []
  const projectGroups = useMemo(
    () => buildProjectGroups(courses, projects),
    [courses, projects],
  )

  const isLoading = coursesResult.waiting || projectsResult.waiting
  const hasError = Result.isFailure(coursesResult) || Result.isFailure(projectsResult)

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>课程与项目</SidebarGroupLabel>
      <SidebarMenu>
        <SidebarMenuButton
          tooltip="创建项目"
          onClick={() => openCreateProjectDialog()}
        >
          <PlusIcon className="size-4 opacity-70" />
          <span>创建项目</span>
        </SidebarMenuButton>

        {isLoading ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled>
              <span className="text-sm text-muted-foreground">
                正在加载课程与项目...
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : hasError ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled>
              <span className="text-sm text-muted-foreground">
                课程或项目加载失败
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : projectGroups.length === 0 ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled>
              <span className="text-sm text-muted-foreground">
                暂无课程和项目
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : (
          projectGroups.map((group) => (
            <CourseProjectGroup key={group.id} group={group} />
          ))
        )}
      </SidebarMenu>
    </SidebarGroup>
  )
}

export default NavProjects
