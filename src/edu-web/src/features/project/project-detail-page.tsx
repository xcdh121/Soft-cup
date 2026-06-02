import { Button } from '@/components/ui/button'
import { chatsAtom, createChatAtom } from '@/data-acess/chat'
import { documentsAtom, refreshDocumentsAtom } from '@/data-acess/document'
import { currentProjectIdAtom } from '@/data-acess/project'
import { studyResourcesAtom } from '@/data-acess/study-resources'
import { useUploadDocumentDialog } from '@/features/document/components/upload-document-dialog'
import { useDocumentPolling } from '@/hooks/use-document-polling'
import { cn } from '@/lib/utils'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useNavigate } from '@tanstack/react-router'
import { Loader2Icon, PlusIcon, RotateCw } from 'lucide-react'
import { useEffect } from 'react'
import { ChatListItem } from './components/chat-list-item'
import { DocumentListItem } from './components/document-list-item'
import {
  GenerationDialog,
  useGenerationDialog,
} from './components/generation-dialog'
import { ProjectHeader } from './components/project-header'
import { StudyResourceListItem } from './components/study-resource-list-item'

const ChatsSection = ({ projectId }: { projectId: string }) => {
  const chatsResult = useAtomValue(chatsAtom(projectId))

  return Result.builder(chatsResult)
    .onInitialOrWaiting(() => (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载聊天...</span>
      </div>
    ))
    .onFailure(() => (
      <div className="text-destructive">聊天加载失败</div>
    ))
    .onSuccess((chats) => (
      <>
        {chats.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            <p>还没有聊天。创建第一个聊天开始使用。</p>
          </div>
        )}

        <ul className="space-y-2">
          {chats.map((chat) => (
            <ChatListItem key={chat.id} chat={chat} />
          ))}
        </ul>
      </>
    ))
    .render()
}

const DocumentsSection = ({ projectId }: { projectId: string }) => {
  const documentsResult = useAtomValue(documentsAtom(projectId))

  return Result.builder(documentsResult)
    .onInitialOrWaiting(() => (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载文档...</span>
      </div>
    ))
    .onFailure(() => (
      <div className="text-destructive">文档加载失败</div>
    ))
    .onSuccess((documents) => (
      <>
        {documents.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            <p>还没有文档。上传第一个文档开始使用。</p>
          </div>
        )}

        <ul className="space-y-2">
          {documents.map((document) => (
            <DocumentListItem key={document.id} document={document} />
          ))}
        </ul>
      </>
    ))
    .render()
}

const AIContentSection = ({ projectId }: { projectId: string }) => {
  const studyResourcesResult = useAtomValue(studyResourcesAtom(projectId))

  return Result.builder(studyResourcesResult)
    .onInitialOrWaiting(() => (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载 AI 内容...</span>
      </div>
    ))
    .onSuccess((resources) => {
      return (
        <>
          {resources.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              <p>还没有 AI 内容。</p>
            </div>
          )}

          <ul className="space-y-2">
            {resources.map((resource) => (
              <StudyResourceListItem
                key={resource.data.id}
                studyResource={resource}
              />
            ))}
          </ul>
        </>
      )
    })
    .render()
}

type ProjectContentProps = {
  projectId: string
}

const ProjectContent = ({ projectId }: ProjectContentProps) => {
  const navigate = useNavigate()

  const createChat = useAtomSet(createChatAtom, {
    mode: 'promise',
  })
  const openUploadDialog = useUploadDocumentDialog((state) => state.open)
  const openGenerationDialog = useGenerationDialog((state) => state.open)
  const refreshDocuments = useAtomSet(refreshDocumentsAtom, {
    mode: 'promise',
  })

  const handleCreateChat = async () => {
    const chat = await createChat({ projectId })
    navigate({
      to: '/dashboard/p/$projectId/c/$chatId',
      params: { projectId, chatId: chat.id },
    })
  }

  const handleCreateDocument = () => {
    openUploadDialog(projectId)
  }

  const handleGenerateResource = () => {
    openGenerationDialog(projectId)
  }

  const handleRefreshDocuments = async () => {
    await refreshDocuments(projectId)
  }

  if (projectId.length === 0) return null

  return (
    <div className="flex flex-1 p-4 gap-4 overflow-hidden min-h-0">
      <div className="flex flex-col w-1/2 border rounded-lg p-4 min-h-0">
        <div className="flex items-center justify-between shrink-0 mb-2">
          <h3 className="text-lg font-semibold">聊天</h3>
          <Button onClick={handleCreateChat} size="sm">
            <PlusIcon className="size-4" />
            <span>新建聊天</span>
          </Button>
        </div>
        <div
          className={cn(
            'flex-1 overflow-y-auto min-h-0',
            '[&::-webkit-scrollbar]:w-2',
            '[&::-webkit-scrollbar-track]:bg-transparent',
            '[&::-webkit-scrollbar-thumb]:bg-muted-foreground/20',
            '[&::-webkit-scrollbar-thumb]:rounded-full',
            '[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/30',
            'dark:[&::-webkit-scrollbar-thumb]:bg-muted-foreground/30',
            'dark:[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/40',
          )}
        >
          <ChatsSection projectId={projectId} />
        </div>
      </div>

      <div className="flex flex-col w-1/2 gap-4 min-h-0">
        {/* Documents */}
        <div className="flex flex-col border rounded-lg p-4 min-h-0 flex-1">
          <div className="flex items-center justify-between shrink-0 mb-2">
            <h3 className="text-lg font-semibold">文档</h3>
            <div className="flex items-center gap-2">
              <Button
                onClick={handleRefreshDocuments}
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0"
              >
                <RotateCw className="size-4" />
              </Button>
              <Button onClick={handleCreateDocument} size="sm">
                <PlusIcon className="size-4" />
                <span>上传</span>
              </Button>
            </div>
          </div>
          <div
            className={cn(
              'flex-1 overflow-y-auto min-h-0',
              '[&::-webkit-scrollbar]:w-2',
              '[&::-webkit-scrollbar-track]:bg-transparent',
              '[&::-webkit-scrollbar-thumb]:bg-muted-foreground/20',
              '[&::-webkit-scrollbar-thumb]:rounded-full',
              '[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/30',
              'dark:[&::-webkit-scrollbar-thumb]:bg-muted-foreground/30',
              'dark:[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/40',
            )}
          >
            <DocumentsSection projectId={projectId} />
          </div>
        </div>

        {/* AI Content */}
        <div className="flex flex-col border rounded-lg p-4 min-h-0 flex-1">
          <div className="flex items-center justify-between shrink-0 mb-2">
            <h3 className="text-lg font-semibold">AI 内容</h3>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={handleGenerateResource}>
                <PlusIcon className="size-4" />
                <span>生成</span>
              </Button>
            </div>
          </div>
          <div
            className={cn(
              'flex-1 overflow-y-auto min-h-0',
              '[&::-webkit-scrollbar]:w-2',
              '[&::-webkit-scrollbar-track]:bg-transparent',
              '[&::-webkit-scrollbar-thumb]:bg-muted-foreground/20',
              '[&::-webkit-scrollbar-thumb]:rounded-full',
              '[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/30',
              'dark:[&::-webkit-scrollbar-thumb]:bg-muted-foreground/30',
              'dark:[&::-webkit-scrollbar-thumb]:hover:bg-muted-foreground/40',
            )}
          >
            <AIContentSection projectId={projectId} />
          </div>
        </div>
      </div>
    </div>
  )
}

type ProjectDetailPageProps = {
  projectId: string
}

export const ProjectDetailPage = ({ projectId }: ProjectDetailPageProps) => {
  const setCurrentProject = useAtomSet(currentProjectIdAtom)

  useEffect(() => {
    setCurrentProject(projectId)
  }, [projectId, setCurrentProject])

  // Poll for document status updates when documents are not ready
  useDocumentPolling(projectId)

  return (
    <div className="flex h-full flex-col max-h-screen">
      <ProjectHeader projectId={projectId} />

      <div className="flex flex-1 flex-col min-h-0 max-h-[calc(100vh-3.5rem)] w-full">
        <ProjectContent projectId={projectId} />
      </div>

      <GenerationDialog />
    </div>
  )
}
