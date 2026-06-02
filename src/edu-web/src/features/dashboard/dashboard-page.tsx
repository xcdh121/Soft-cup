import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { FolderIcon, PlusIcon } from 'lucide-react'
import { projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export const DashboardPage = () => {
  const projectsResult = useAtomValue(projectsAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const hasProjects =
    Result.isSuccess(projectsResult) && projectsResult.value.length > 0

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
            <p className="text-muted-foreground mt-2">
              管理项目并整理你的学习资料
            </p>
          </div>
          {hasProjects && (
            <Button onClick={() => openCreateProjectDialog()}>
              <PlusIcon className="h-4 w-4 mr-2" />
              新建项目
            </Button>
          )}
        </div>

        {Result.builder(projectsResult)
          .onInitialOrWaiting(() => (
            <div className="text-center py-12">
              <p className="text-muted-foreground">正在加载项目...</p>
            </div>
          ))
          .onFailure(() => (
            <div className="text-center py-12">
              <p className="text-destructive">项目加载失败</p>
            </div>
          ))
          .onSuccess((projects) => {
            if (projects.length === 0) {
              return (
                <Card>
                  <CardHeader>
                    <CardTitle>还没有项目</CardTitle>
                    <CardDescription>
                      创建第一个项目开始使用
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button onClick={() => openCreateProjectDialog()}>
                      <PlusIcon className="h-4 w-4 mr-2" />
                      创建项目
                    </Button>
                  </CardContent>
                </Card>
              )
            }

            return (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {projects.map((project) => (
                  <Card
                    key={project.id}
                    className="hover:shadow-md transition-shadow"
                  >
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <FolderIcon className="h-5 w-5" />
                        <Link
                          to="/dashboard/p/$projectId"
                          params={{ projectId: project.id }}
                          className="hover:underline"
                        >
                          {project.name}
                        </Link>
                      </CardTitle>
                      {project.description && (
                        <CardDescription>{project.description}</CardDescription>
                      )}
                    </CardHeader>
                    <CardContent>
                      <Link
                        to="/dashboard/p/$projectId"
                        params={{ projectId: project.id }}
                      >
                        <Button variant="outline" className="w-full">
                          打开项目
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )
          })
          .render()}
      </div>
    </div>
  )
}
