import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { FileTextIcon, Loader2Icon, PlusIcon, RotateCwIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { documentsAtom, refreshDocumentsAtom } from '@/data-acess/document'
import { currentProjectIdAtom } from '@/data-acess/project'
import { useUploadDocumentDialog } from '@/features/document/components/upload-document-dialog'
import { DocumentBookCard } from '@/features/document/components/document-book-card'
import { useDocumentPolling } from '@/hooks/use-document-polling'
import { supabase } from '@/lib/supabase'

type CustomDocumentLearningPageProps = {
  projectId: string
}

export const CustomDocumentLearningPage = ({
  projectId,
}: CustomDocumentLearningPageProps) => {
  const documentsResult = useAtomValue(documentsAtom(projectId))
  const setCurrentProject = useAtomSet(currentProjectIdAtom)
  const refreshDocuments = useAtomSet(refreshDocumentsAtom, { mode: 'promise' })
  const openUploadDialog = useUploadDocumentDialog((state) => state.open)
  const [accessToken, setAccessToken] = useState<string | null | undefined>()

  useEffect(() => {
    setCurrentProject(projectId)
  }, [projectId, setCurrentProject])

  useEffect(() => {
    let cancelled = false

    void supabase.auth.getSession().then(({ data }) => {
      if (!cancelled) setAccessToken(data.session?.access_token ?? null)
    })

    return () => {
      cancelled = true
    }
  }, [])

  useDocumentPolling(projectId)

  return (
    <main className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-6 p-6 lg:p-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            自定义文档学习
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            上传并处理自己的文档，处理完成后可进入阅读界面进行 PDF 阅读与 AI
            问答。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refreshDocuments(projectId)}
          >
            <RotateCwIcon className="size-4" />
            刷新
          </Button>
          <Button size="sm" onClick={() => openUploadDialog(projectId)}>
            <PlusIcon className="size-4" />
            上传文档
          </Button>
        </div>
      </header>

      <section className="min-h-0 flex-1 rounded-xl border bg-card p-5 shadow-sm sm:p-6">
        {Result.builder(documentsResult)
          .onInitialOrWaiting(() => (
            <div className="flex min-h-56 items-center justify-center gap-2 text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              <span>正在加载文档...</span>
            </div>
          ))
          .onFailure(() => (
            <div className="flex min-h-56 items-center justify-center text-destructive">
              文档加载失败，请稍后重试
            </div>
          ))
          .onSuccess((documents) =>
            documents.length === 0 ? (
              <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                <FileTextIcon className="size-10 opacity-60" />
                <div>
                  <p className="font-medium text-foreground">
                    还没有自定义文档
                  </p>
                  <p className="mt-1 text-sm">
                    上传 PDF、DOCX 或 TXT 文档开始学习。
                  </p>
                </div>
                <Button size="sm" onClick={() => openUploadDialog(projectId)}>
                  <PlusIcon className="size-4" />
                  上传第一个文档
                </Button>
              </div>
            ) : (
              <ul className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 sm:gap-x-7 lg:grid-cols-4 xl:grid-cols-5">
                {documents.map((document) => (
                  <DocumentBookCard
                    key={document.id}
                    accessToken={accessToken}
                    document={document}
                  />
                ))}
              </ul>
            ),
          )
          .render()}
      </section>
    </main>
  )
}
