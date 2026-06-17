import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'
import { MindMapView } from './mind-map-view'
import { mindMapAtom, refreshMindMapAtom } from '@/data-acess/mind-map'

type MindMapContentProps = {
  mindMapId: string
  projectId: string
  className?: string
}

export const MindMapContent = ({
  mindMapId,
  projectId,
  className,
}: MindMapContentProps) => {
  const mindMapResult = useAtomValue(mindMapAtom(`${projectId}:${mindMapId}`))
  const refreshMindMap = useAtomSet(refreshMindMapAtom, { mode: 'promise' })

  useEffect(() => {
    if (!Result.isSuccess(mindMapResult)) return
    if (!mindMapResult.value) return

    const mapData = mindMapResult.value.map_data as
      | { nodes?: unknown[]; edges?: unknown[] }
      | null
      | undefined
    if ((mapData?.nodes?.length ?? 0) > 0) return

    const intervalId = window.setInterval(() => {
      refreshMindMap({ projectId, mindMapId }).catch(() => {
        // Keep the current mind map visible if a transient refresh fails.
      })
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [mindMapId, mindMapResult, projectId, refreshMindMap])

  return Result.builder(mindMapResult)
    .onSuccess((mindMap) => {
      if (!mindMap) {
        return (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <p>未找到思维导图</p>
          </div>
        )
      }

      const mapData = mindMap.map_data as {
        nodes: Array<{
          id: string
          type?: string
          position: { x: number; y: number }
          data: { label: string; [key: string]: unknown }
        }>
        edges: Array<{
          id: string
          source: string
          target: string
          label?: string | null
          type?: string
        }>
      }

      return (
        <div className={`flex flex-col h-full ${className || ''}`}>
          {mindMap.description && (
            <div className="text-muted-foreground text-sm mb-4">
              {mindMap.description}
            </div>
          )}
          <div className="flex-1 min-h-0 border rounded-lg overflow-hidden">
            {mapData.nodes.length > 0 ? (
              <MindMapView mapData={mapData} />
            ) : (
              <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
                <Loader2Icon className="size-4 animate-spin" />
                <span>正在生成思维导图...</span>
              </div>
            )}
          </div>
        </div>
      )
    })
    .onInitialOrWaiting(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载思维导图...</span>
      </div>
    ))
    .onFailure(() => (
      <div className="flex flex-1 items-center justify-center gap-2 text-destructive">
        <span>思维导图加载失败</span>
      </div>
    ))
    .render()
}
