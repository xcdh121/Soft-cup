import { useForm } from 'react-hook-form'
import { effectTsResolver } from '@hookform/resolvers/effect-ts'
import { create } from 'zustand'
import { Result, useAtom, useAtomValue } from '@effect-atom/atom-react'
import * as S from 'effect/Schema'
import { useEffect } from 'react'
import type { ProjectDto } from '@/integrations/api/client'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { coursesAtom } from '@/data-acess/course-library'
import { upsertProjectAtom } from '@/data-acess/project'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type CreateProjectDialogStore = {
  isOpen: boolean
  project?: ProjectDto
  open: (project?: ProjectDto) => void
  close: () => void
  toggle: () => void
}

export const useCreateProjectDialog = create<CreateProjectDialogStore>(
  (set) => ({
    isOpen: false,
    open: (project?: ProjectDto) =>
      set({ isOpen: true, project: project ?? undefined }),
    close: () => set({ isOpen: false }),
    toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  }),
)

const schema = S.Struct({
  name: S.String,
  description: S.optional(S.String),
  language_code: S.String,
  course_id: S.String,
})

type UpsertProjectSchema = typeof schema.Type

const languages = [
  { code: 'cs', name: '捷克语' },
  { code: 'en', name: '英语' },
  { code: 'es', name: '西班牙语' },
  { code: 'fr', name: '法语' },
  { code: 'de', name: '德语' },
  { code: 'it', name: '意大利语' },
  { code: 'pt', name: '葡萄牙语' },
  { code: 'ru', name: '俄语' },
  { code: 'zh', name: '中文' },
]

export function UpsertProjectDialog() {
  const { isOpen, close, project } = useCreateProjectDialog()
  const coursesResult = useAtomValue(coursesAtom)

  const [upsertProjectResult, upsertProject] = useAtom(upsertProjectAtom, {
    mode: 'promise',
  })
  const isLoading = upsertProjectResult.waiting
  const courses = Result.isSuccess(coursesResult) ? coursesResult.value : []

  const form = useForm<UpsertProjectSchema>({
    resolver: effectTsResolver(schema),
    defaultValues: {
      name: '',
      description: '',
      language_code: 'cs',
      course_id: 'none',
    },
  })

  useEffect(() => {
    if (isOpen) {
      form.reset({
        name: project?.name ?? '',
        description: project?.description ?? '',
        language_code: project?.language_code ?? 'cs',
        course_id: project?.course_id ?? 'none',
      })
    }
  }, [isOpen, project, form])

  const handleClose = () => {
    close()
    form.reset()
  }

  const onSubmit = async (data: UpsertProjectSchema) => {
    await upsertProject({
      ...data,
      course_id: data.course_id === 'none' ? null : data.course_id,
      id: project?.id,
    })
    handleClose()
  }

  const isEditMode = !!project

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? '编辑项目' : '创建项目'}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? '更新项目详情。'
              : '创建新项目，用来整理学习资料和对话。'}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>名称</FormLabel>
                  <FormControl>
                    <Input placeholder="例如：我的项目" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>描述（可选）</FormLabel>
                  <FormControl>
                    <Input placeholder="例如：项目描述" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="language_code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>语言</FormLabel>
                  <FormControl>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="选择语言" />
                      </SelectTrigger>
                      <SelectContent>
                        {languages.map((language) => (
                          <SelectItem key={language.code} value={language.code}>
                            {language.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="course_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>所属课程</FormLabel>
                  <FormControl>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="选择课程" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">暂不绑定课程</SelectItem>
                        {courses.map((course) => (
                          <SelectItem key={course.id} value={course.id}>
                            {course.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <p className="text-xs text-muted-foreground">
                    选择后，左侧导航会按“课程 → 项目”归类显示。
                  </p>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isLoading}
              >
                取消
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading
                  ? isEditMode
                    ? '正在更新...'
                    : '正在创建...'
                  : isEditMode
                    ? '更新项目'
                    : '创建项目'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
