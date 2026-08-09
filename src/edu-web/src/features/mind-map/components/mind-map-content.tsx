import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'
import { MindMapView, normalizeMindMapData } from './mind-map-view'
import { Response } from '@/components/ai-elements/response'
import {
  mindMapAtom,
  mindMapProgressAtom,
  refreshMindMapAtom,
} from '@/data-acess/mind-map'

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
  const streamProgress = useAtomValue(mindMapProgressAtom)
  const refreshMindMap = useAtomSet(refreshMindMapAtom, { mode: 'promise' })

  useEffect(() => {
    if (!Result.isSuccess(mindMapResult)) return

    const mapData = mindMapResult.value.map_data as
      | { nodes?: Array<unknown>; edges?: Array<unknown> }
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
      const rawMapData =
        streamProgress?.mindMapId === mindMapId &&
        streamProgress.nodes.length > 0
          ? {
              nodes: streamProgress.nodes.map((node) => ({
                id: String(node.id),
                position: node.position as { x: number; y: number },
                data: {
                  ...((node.data as Record<string, unknown> | undefined) ?? {}),
                  label: String(node.label ?? ''),
                },
              })),
              edges: streamProgress.edges.map((edge) => ({
                id: String(edge.id),
                source: String(edge.source),
                target: String(edge.target),
                label: edge.label == null ? null : String(edge.label),
              })),
            }
          : mindMap.map_data
      const mapData = normalizeMindMapData(rawMapData)

      return (
        <div className={`flex flex-col h-full ${className || ''}`}>
          {mindMap.description && (
            <Response className="text-muted-foreground text-sm mb-4">
              {mindMap.description}
            </Response>
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
