import { useCallback, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { create } from 'zustand'
import { FileIcon, Loader2Icon, UploadIcon, XIcon } from 'lucide-react'
import { useAtom } from '@effect-atom/atom-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import { uploadDocumentAtom } from '@/data-acess/document'

type UploadDocumentDialogStore = {
  isOpen: boolean
  projectId?: string
  open: (projectId: string) => void
  close: () => void
}

export const useUploadDocumentDialog = create<UploadDocumentDialogStore>(
  (set) => ({
    isOpen: false,
    open: (projectId: string) => set({ isOpen: true, projectId }),
    close: () => set({ isOpen: false, projectId: undefined }),
  }),
)

export function UploadDocumentDialog() {
  const { isOpen, projectId, close } = useUploadDocumentDialog()
  const [files, setFiles] = useState<Array<File>>([])
  const [uploadProgress, setUploadProgress] = useState<number>(0)

  const [uploadDocumentResult, uploadDocument] = useAtom(uploadDocumentAtom, {
    mode: 'promise',
  })

  const onDrop = useCallback((acceptedFiles: Array<File>) => {
    setFiles((prev) => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
  })

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleClose = () => {
    // Reset state when closing
    setFiles([])
    close()
  }

  // Cleanup on unmount or when dialog closes
  useEffect(() => {
    if (!isOpen) {
      setFiles([])
    }
    return () => {
      // Cleanup on unmount
      setFiles([])
    }
  }, [isOpen])

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 字节'
    const k = 1024
    const sizes = ['字节', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
  }

  const handleUpload = async () => {
    if (files.length === 0 || !projectId) return
    setUploadProgress(0)
    try {
      await uploadDocument({
        projectId: projectId,
        files,
      })
      setUploadProgress(100)
      setTimeout(() => {
        handleClose()
      }, 500)
    } catch (error) {
      console.error('Upload failed:', error)
      setUploadProgress(0)
      // Error is already handled by the atom
    }
  }

  // Reset progress when dialog closes
  useEffect(() => {
    if (!isOpen) {
      setUploadProgress(0)
    }
  }, [isOpen])

  if (!projectId) return null

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>上传文档</DialogTitle>
          <DialogDescription>
            将文件拖放到这里，或点击选择文件。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div
            {...getRootProps()}
            className={cn(
              'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-muted-foreground/50',
            )}
          >
            <input {...getInputProps()} />
            <UploadIcon className="mx-auto size-12 mb-4 text-muted-foreground" />
            {isDragActive ? (
              <p className="text-sm font-medium">把文件放到这里...</p>
            ) : (
              <div className="space-y-2">
                <p className="text-sm font-medium">
                  将文件拖放到这里，或点击选择
                </p>
                <p className="text-xs text-muted-foreground">
                  支持 PDF、DOCX、TXT 等文档格式
                </p>
              </div>
            )}
          </div>

          {files.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">已选择文件：</p>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {files.map((file, index) => (
                  <div
                    key={`${file.name}-${index}`}
                    className="flex items-center gap-3 p-3 bg-muted rounded-lg overflow-hidden"
                  >
                    <FileIcon className="size-5 shrink-0 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <p
                        className="text-sm font-medium truncate max-w-[300px]"
                        title={file.name}
                      >
                        {file.name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate w-full">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0 size-8 flex-shrink-0"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeFile(index)
                      }}
                    >
                      <XIcon className="size-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {uploadDocumentResult.waiting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">正在上传...</span>
                <span className="text-muted-foreground">
                  {uploadProgress > 0 ? `${uploadProgress}%` : '处理中...'}
                </span>
              </div>
              <Progress
                value={
                  uploadProgress || (uploadDocumentResult.waiting ? 50 : 0)
                }
                className="h-2"
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            取消
          </Button>
          <Button
            onClick={handleUpload}
            disabled={files.length === 0 || uploadDocumentResult.waiting}
          >
            {uploadDocumentResult.waiting && (
              <Loader2Icon className="size-4 animate-spin" />
            )}
            <span>上传</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
