import {
  CircleAlertIcon,
  Loader2Icon,
  PlayIcon,
  RefreshCwIcon,
  SparklesIcon,
  Volume2Icon,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AvatarPlatform, {
  PlayerEvents,
  SDKEvents,
} from '../../../../avatar-sdk-web_3.2.3.1002/esm/index.js'
import { prepareSpeechText, splitSpeechText } from './digital-avatar-text'
import { Button } from '@/components/ui/button'
import { env } from '@/env'

type AvatarStatus = 'disabled' | 'connecting' | 'ready' | 'speaking' | 'error'

type DigitalAvatarPanelProps = {
  assistantMessageId: string | null
  assistantText: string
  isStreaming: boolean
}

const avatarConfig = {
  serverUrl:
    env.VITE_AVATAR_SERVER_URL ??
    'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
  appId: env.VITE_AVATAR_APP_ID,
  apiKey: env.VITE_AVATAR_API_KEY,
  apiSecret: env.VITE_AVATAR_API_SECRET,
  sceneId: env.VITE_AVATAR_SCENE_ID,
  avatarId: env.VITE_AVATAR_ID,
  vcn: env.VITE_AVATAR_VCN,
}

const isAvatarConfigured = Object.values(avatarConfig).every(Boolean)

const getErrorMessage = (error: unknown) => {
  if (error instanceof Error) return error.message
  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message)
  }
  return String(error || '数字人服务发生未知错误')
}

const statusCopy: Record<AvatarStatus, string> = {
  disabled: '等待配置',
  connecting: '正在连接',
  ready: '已就绪',
  speaking: '正在讲解',
  error: '连接异常',
}

export const DigitalAvatarPanel = ({
  assistantMessageId,
  assistantText,
  isStreaming,
}: DigitalAvatarPanelProps) => {
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const avatarRef = useRef<AvatarPlatform | null>(null)
  const isReadyRef = useRef(false)
  const pendingTextRef = useRef<string | null>(null)
  const isSpeakingRef = useRef(false)
  const driveRequestIdRef = useRef(0)
  const lastDrivenMessageIdRef = useRef<string | null>(assistantMessageId)
  const [instanceKey, setInstanceKey] = useState(0)
  const [status, setStatus] = useState<AvatarStatus>(
    isAvatarConfigured ? 'connecting' : 'disabled',
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [needsInteraction, setNeedsInteraction] = useState(false)

  const speechText = useMemo(
    () => prepareSpeechText(assistantText),
    [assistantText],
  )

  const driveText = useCallback(async (text: string) => {
    const avatar = avatarRef.current
    if (!avatar || !isReadyRef.current) {
      pendingTextRef.current = text
      return
    }

    const requestId = ++driveRequestIdRef.current
    const chunks = splitSpeechText(text)

    try {
      if (isSpeakingRef.current) {
        await avatar.interrupt()
      }
      isSpeakingRef.current = true
      setErrorMessage(null)
      setStatus('speaking')

      for (const chunk of chunks) {
        if (requestId !== driveRequestIdRef.current) return
        await avatar.writeText(chunk, {
          nlp: false,
          avatar_dispatch: { interactive_mode: 0 },
        })
      }
    } catch (error) {
      if (requestId !== driveRequestIdRef.current) return
      isSpeakingRef.current = false
      setStatus('error')
      setErrorMessage(getErrorMessage(error))
    }
  }, [])

  useEffect(() => {
    if (!isAvatarConfigured || !wrapperRef.current) return

    let disposed = false
    const avatar = new AvatarPlatform()
    avatarRef.current = avatar
    isReadyRef.current = false
    setStatus('connecting')
    setErrorMessage(null)

    avatar
      .on(SDKEvents.connected, () => {
        if (!disposed) setStatus('ready')
      })
      .on(SDKEvents.frame_start, () => {
        if (!disposed) {
          isSpeakingRef.current = true
          setStatus('speaking')
        }
      })
      .on(SDKEvents.frame_stop, () => {
        if (!disposed) {
          isSpeakingRef.current = false
          setStatus('ready')
        }
      })
      .on(SDKEvents.disconnected, (event: unknown) => {
        if (!disposed) {
          isReadyRef.current = false
          isSpeakingRef.current = false
          setStatus('error')
          setErrorMessage(
            event ? getErrorMessage(event) : '数字人连接已断开，请重试',
          )
        }
      })
      .on(SDKEvents.error, (error: unknown) => {
        if (!disposed) {
          isReadyRef.current = false
          isSpeakingRef.current = false
          setStatus('error')
          setErrorMessage(getErrorMessage(error))
        }
      })

    const player = avatar.player ?? avatar.createPlayer()
    player.on(PlayerEvents.playNotAllowed, () => {
      if (!disposed) setNeedsInteraction(true)
    })
    player.on(PlayerEvents.error, (error: unknown) => {
      if (!disposed) {
        setStatus('error')
        setErrorMessage(getErrorMessage(error))
      }
    })

    avatar.setApiInfo({
      serverUrl: avatarConfig.serverUrl,
      appId: avatarConfig.appId!,
      apiKey: avatarConfig.apiKey!,
      apiSecret: avatarConfig.apiSecret!,
      sceneId: avatarConfig.sceneId!,
    })
    avatar.setGlobalParams({
      stream: { protocol: 'xrtc' },
      avatar: {
        avatar_id: avatarConfig.avatarId!,
        width: 720,
        height: 1280,
      },
      tts: { vcn: avatarConfig.vcn! },
    })

    void avatar
      .start({ wrapper: wrapperRef.current })
      .then(() => {
        if (disposed) return
        isReadyRef.current = true
        setStatus('ready')
        const pendingText = pendingTextRef.current
        pendingTextRef.current = null
        if (pendingText) void driveText(pendingText)
      })
      .catch((error: unknown) => {
        if (!disposed) {
          setStatus('error')
          setErrorMessage(getErrorMessage(error))
        }
      })

    return () => {
      disposed = true
      avatarRef.current = null
      isReadyRef.current = false
      isSpeakingRef.current = false
      driveRequestIdRef.current += 1
      avatar.destroy()
    }
  }, [driveText, instanceKey])

  useEffect(() => {
    if (
      !isAvatarConfigured ||
      isStreaming ||
      !assistantMessageId ||
      !speechText ||
      assistantMessageId === lastDrivenMessageIdRef.current
    ) {
      return
    }

    // The stream status is authoritative. The short debounce also protects
    // against backends that send text deltas without an explicit status event.
    const timer = window.setTimeout(() => {
      lastDrivenMessageIdRef.current = assistantMessageId
      void driveText(speechText)
    }, 500)

    return () => window.clearTimeout(timer)
  }, [assistantMessageId, driveText, isStreaming, speechText])

  const resumePlayback = async () => {
    try {
      await avatarRef.current?.player?.resume()
      setNeedsInteraction(false)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  return (
    <aside className="hidden min-h-0 bg-background xl:flex xl:flex-col">
      <div className="border-b px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SparklesIcon className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">AI 数字人</h2>
          </div>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={`size-1.5 rounded-full ${
                status === 'ready'
                  ? 'bg-emerald-500'
                  : status === 'speaking'
                    ? 'animate-pulse bg-primary'
                    : status === 'error'
                      ? 'bg-destructive'
                      : 'bg-muted-foreground'
              }`}
            />
            {statusCopy[status]}
          </span>
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          大模型回答完成后，数字人会自动为你讲解。
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border bg-neutral-950 shadow-sm">
          <div ref={wrapperRef} className="size-full min-h-80" />

          {status === 'connecting' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-neutral-950 text-neutral-200">
              <Loader2Icon className="size-6 animate-spin" />
              <span className="text-sm">正在连接数字人...</span>
            </div>
          )}

          {status === 'disabled' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center text-neutral-200">
              <CircleAlertIcon className="mb-3 size-7 text-amber-400" />
              <div className="text-sm font-medium">数字人 SDK 尚未配置</div>
              <p className="mt-2 text-xs leading-5 text-neutral-400">
                请在根目录 .env 中填写 VITE_AVATAR_* 配置后重启前端。
              </p>
            </div>
          )}

          {needsInteraction && (
            <div className="absolute inset-x-4 bottom-4 rounded-lg border border-white/10 bg-black/75 p-3 text-white backdrop-blur">
              <p className="text-xs leading-5">
                浏览器阻止了有声自动播放，请点击启用声音。
              </p>
              <Button
                className="mt-2 w-full"
                size="sm"
                onClick={() => void resumePlayback()}
              >
                <Volume2Icon className="size-4" />
                启用声音
              </Button>
            </div>
          )}
        </div>

        {errorMessage && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
            {errorMessage}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!isAvatarConfigured || !speechText}
            onClick={() => void driveText(speechText)}
          >
            <PlayIcon className="size-4" />
            重播回答
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!isAvatarConfigured}
            onClick={() => setInstanceKey((key) => key + 1)}
          >
            <RefreshCwIcon className="size-4" />
            重新连接
          </Button>
        </div>
      </div>
    </aside>
  )
}
