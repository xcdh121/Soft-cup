import { CheckCircle2Icon, CircleAlertIcon, FileTextIcon } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

export type PdfUploadProgressValue = {
  fileName: string
  label: string
  detail: string
  progress: number
  state: 'active' | 'success' | 'error'
}

export const PdfUploadProgress = ({
  value,
}: {
  value: PdfUploadProgressValue
}) => (
  <div
    className="w-full space-y-2.5 border-b px-3 py-3"
    data-testid="pdf-upload-progress"
    role="status"
    aria-live="polite"
  >
    <div className="flex items-start gap-2.5">
      <div
        className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md ${
          value.state === 'error'
            ? 'bg-destructive/10 text-destructive'
            : value.state === 'success'
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              : 'bg-primary/10 text-primary'
        }`}
      >
        {value.state === 'error' ? (
          <CircleAlertIcon className="size-4" />
        ) : value.state === 'success' ? (
          <CheckCircle2Icon className="size-4" />
        ) : (
          <FileTextIcon className="size-4" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span className="truncate font-medium">{value.label}</span>
          <span className="shrink-0 tabular-nums text-muted-foreground text-xs">
            {value.progress}%
          </span>
        </div>
        <div className="mt-0.5 truncate text-muted-foreground text-xs">
          {value.fileName} · {value.detail}
        </div>
      </div>
    </div>
    <Progress
      aria-label={`PDF 处理进度 ${value.progress}%`}
      className={
        value.state === 'error'
          ? '[&_[data-slot=progress-indicator]]:bg-destructive'
          : value.state === 'success'
            ? '[&_[data-slot=progress-indicator]]:bg-emerald-500'
            : undefined
      }
      value={value.progress}
    />
  </div>
)
