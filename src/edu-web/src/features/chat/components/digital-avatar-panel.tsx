import {
  CircleAlertIcon,
  Loader2Icon,
  MicIcon,
  RefreshCwIcon,
  SendIcon,
  SparklesIcon,
  SquareIcon,
  Volume2Icon,
  XIcon,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import digitalAvatarCover from '../../../../../source/5.png'
import AvatarPlatform, {
  PlayerEvents,
  RecorderEvents,
  SDKEvents,
} from '../../../../avatar-sdk-web_3.2.3.1002/esm/index.js'
import {
  getAvatarEventStatus,
  getAvatarEventText,
} from './digital-avatar-event'
import type { Recorder } from '../../../../avatar-sdk-web_3.2.3.1002/esm/index.js'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { Response } from '@/components/ai-elements/response'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { env } from '@/env'

type AvatarStatus =
  | 'disabled'
  | 'connecting'
  | 'ready'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error'

type FloatingPosition = {
  x: number
  y: number
}

type DragState = {
  pointerId: number
  startX: number
  startY: number
  originX: number
  originY: number
  moved: boolean
}

type ConversationMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const floatingBallSize = 64
const viewportMargin = 16
const createMessageId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const clampPosition = (
  position: FloatingPosition,
  viewport: { width: number; height: number },
): FloatingPosition => ({
  x: Math.min(
    Math.max(viewportMargin, position.x),
    Math.max(
      viewportMargin,
      viewport.width - floatingBallSize - viewportMargin,
    ),
  ),
  y: Math.min(
    Math.max(viewportMargin, position.y),
    Math.max(
      viewportMargin,
      viewport.height - floatingBallSize - viewportMargin,
    ),
  ),
})

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
  ready: '可以提问',
  listening: '正在聆听',
  thinking: '正在思考',
  speaking: '正在讲解',
  error: '连接异常',
}

export const DigitalAvatarPanel = () => {
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const avatarRef = useRef<AvatarPlatform | null>(null)
  const recorderRef = useRef<Recorder | null>(null)
  const isReadyRef = useRef(false)
  const isSpeakingRef = useRef(false)
  const isRecordingRef = useRef(false)
  const dragStateRef = useRef<DragState | null>(null)
  const suppressClickRef = useRef(false)
  const pendingAssistantMessageIdRef = useRef<string | null>(null)
  const voiceQuestionMessageIdRef = useRef<string | null>(null)
  const conversationEndRef = useRef<HTMLDivElement | null>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [ballPosition, setBallPosition] = useState<FloatingPosition | null>(
    null,
  )
  const [viewport, setViewport] = useState({ width: 0, height: 0 })
  const [instanceKey, setInstanceKey] = useState(0)
  const [question, setQuestion] = useState('')
  const [conversation, setConversation] = useState<Array<ConversationMessage>>([
    {
      id: 'welcome-message',
      role: 'assistant',
      content: '您好，我是知识库数字人导师。您可以向我咨询课程知识或平台操作。',
    },
  ])
  const [isThinking, setIsThinking] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [status, setStatus] = useState<AvatarStatus>(
    isAvatarConfigured ? 'connecting' : 'disabled',
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [needsInteraction, setNeedsInteraction] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(false)

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [conversation, isThinking])

  useEffect(() => {
    const updateViewport = () => {
      const nextViewport = {
        width: window.innerWidth,
        height: window.innerHeight,
      }
      setViewport(nextViewport)
      setBallPosition((current) =>
        clampPosition(
          current ?? {
            x: nextViewport.width - floatingBallSize - 28,
            y: nextViewport.height - floatingBallSize - 28,
          },
          nextViewport,
        ),
      )
    }

    updateViewport()
    window.addEventListener('resize', updateViewport)
    return () => window.removeEventListener('resize', updateViewport)
  }, [])

  useEffect(() => {
    if (!isOpen || !isAvatarConfigured || !wrapperRef.current) return

    let disposed = false
    const avatar = new AvatarPlatform()
    avatarRef.current = avatar
    isReadyRef.current = false
    setStatus('connecting')
    setErrorMessage(null)
    setNeedsInteraction(false)
    setSoundEnabled(false)

    avatar
      .on(SDKEvents.nlp, (event: unknown) => {
        if (disposed) return
        const text = getAvatarEventText(event)
        if (text) {
          const messageId =
            pendingAssistantMessageIdRef.current ?? createMessageId('assistant')
          pendingAssistantMessageIdRef.current = messageId
          setConversation((current) => {
            const existing = current.findIndex(
              (message) => message.id === messageId,
            )
            if (existing === -1) {
              return [
                ...current,
                { id: messageId, role: 'assistant', content: text },
              ]
            }
            return current.map((message, index) =>
              index === existing ? { ...message, content: text } : message,
            )
          })
        }
        if (getAvatarEventStatus(event) === 2) setIsThinking(false)
      })
      .on(SDKEvents.asr, (event: unknown) => {
        if (disposed) return
        const text = getAvatarEventText(event)
        if (text) {
          const messageId =
            voiceQuestionMessageIdRef.current ?? createMessageId('voice-user')
          voiceQuestionMessageIdRef.current = messageId
          setConversation((current) => {
            const existing = current.findIndex(
              (message) => message.id === messageId,
            )
            if (existing === -1) {
              return [
                ...current,
                { id: messageId, role: 'user', content: text },
              ]
            }
            return current.map((message, index) =>
              index === existing ? { ...message, content: text } : message,
            )
          })
        }
      })
      .on(SDKEvents.frame_start, () => {
        if (!disposed) {
          isSpeakingRef.current = true
          setIsThinking(false)
          setStatus('speaking')
        }
      })
      .on(SDKEvents.frame_stop, () => {
        if (!disposed) {
          isSpeakingRef.current = false
          setIsThinking(false)
          setStatus('ready')
        }
      })
      .on(SDKEvents.disconnected, (event: unknown) => {
        if (!disposed) {
          isReadyRef.current = false
          isSpeakingRef.current = false
          isRecordingRef.current = false
          setIsRecording(false)
          setIsThinking(false)
          setStatus('error')
          setErrorMessage(
            event ? getErrorMessage(event) : '数字人连接已断开，请重新连接',
          )
        }
      })
      .on(SDKEvents.error, (error: unknown) => {
        if (!disposed) {
          isRecordingRef.current = false
          setIsRecording(false)
          setIsThinking(false)
          setStatus('error')
          setErrorMessage(getErrorMessage(error))
        }
      })

    const player = avatar.player ?? avatar.createPlayer()
    player.volume = 1
    player.on(PlayerEvents.playNotAllowed, () => {
      if (!disposed) {
        setNeedsInteraction(true)
        setSoundEnabled(false)
      }
    })
    player.on(PlayerEvents.playing, () => {
      if (!disposed) setSoundEnabled(!player.muted)
    })
    player.on(PlayerEvents.error, (error: unknown) => {
      if (!disposed) {
        setStatus('error')
        setErrorMessage(getErrorMessage(error))
      }
    })

    const recorder = avatar.createRecorder({ sampleRate: 16000 })
    recorderRef.current = recorder
    recorder.on(RecorderEvents.ended, () => {
      if (!disposed) {
        isRecordingRef.current = false
        setIsRecording(false)
        setIsThinking(true)
        setStatus('thinking')
      }
    })
    recorder.on(RecorderEvents.error, (error: unknown) => {
      if (!disposed) {
        isRecordingRef.current = false
        setIsRecording(false)
        setIsThinking(false)
        setStatus('ready')
        setErrorMessage(`无法使用麦克风：${getErrorMessage(error)}`)
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
      avatar_dispatch: {
        interactive_mode: 1,
        content_analysis: 1,
      },
      air: { air: 1, add_nonsemantic: 1 },
    })

    void avatar
      .start({ wrapper: wrapperRef.current })
      .then(() => {
        if (disposed) return
        isReadyRef.current = true
        setStatus('ready')
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
      recorderRef.current = null
      isReadyRef.current = false
      isSpeakingRef.current = false
      isRecordingRef.current = false
      avatar.destroy()
    }
  }, [instanceKey, isOpen])

  const resumePlayback = useCallback(async () => {
    const player = avatarRef.current?.player
    if (!player) return false

    try {
      player.volume = 1
      player.muted = false
      await player.resume()
      setNeedsInteraction(false)
      setSoundEnabled(true)
      return true
    } catch (error) {
      setSoundEnabled(false)
      setErrorMessage(getErrorMessage(error))
      return false
    }
  }, [])

  const askQuestion = useCallback(async () => {
    const text = question.trim()
    const avatar = avatarRef.current
    if (!text || !avatar || !isReadyRef.current || isRecordingRef.current) {
      return
    }

    try {
      await resumePlayback()
      if (isSpeakingRef.current) await avatar.interrupt()
      pendingAssistantMessageIdRef.current = null
      voiceQuestionMessageIdRef.current = null
      setConversation((current) => [
        ...current,
        { id: createMessageId('user'), role: 'user', content: text },
      ])
      setQuestion('')
      setErrorMessage(null)
      setIsThinking(true)
      setStatus('thinking')
      await avatar.writeText(text, {
        nlp: true,
        avatar_dispatch: { interactive_mode: 1 },
      })
    } catch (error) {
      setIsThinking(false)
      setStatus('error')
      setErrorMessage(getErrorMessage(error))
    }
  }, [question, resumePlayback])

  const toggleRecording = useCallback(async () => {
    const avatar = avatarRef.current
    const recorder = recorderRef.current
    if (!avatar || !recorder || !isReadyRef.current) return

    try {
      await resumePlayback()
      if (isRecordingRef.current) {
        await recorder.stopRecord()
        isRecordingRef.current = false
        setIsRecording(false)
        setIsThinking(true)
        setStatus('thinking')
        return
      }

      if (isSpeakingRef.current) await avatar.interrupt()
      voiceQuestionMessageIdRef.current = null
      pendingAssistantMessageIdRef.current = null
      setErrorMessage(null)
      setIsThinking(false)
      await recorder.startRecord(
        30_000,
        () => {
          isRecordingRef.current = false
          setIsRecording(false)
          setIsThinking(true)
          setStatus('thinking')
        },
        { nlp: true },
      )
      isRecordingRef.current = true
      setIsRecording(true)
      setStatus('listening')
    } catch (error) {
      isRecordingRef.current = false
      setIsRecording(false)
      setStatus('ready')
      setErrorMessage(
        `语音提问启动失败，请检查麦克风权限和 HTTPS 环境：${getErrorMessage(error)}`,
      )
    }
  }, [resumePlayback])

  const unavailable =
    !isAvatarConfigured || status === 'connecting' || status === 'error'

  const handleBallPointerDown = (
    event: ReactPointerEvent<HTMLButtonElement>,
  ) => {
    if (event.button !== 0) return
    const rect = event.currentTarget.getBoundingClientRect()
    dragStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: ballPosition?.x ?? rect.left,
      originY: ballPosition?.y ?? rect.top,
      moved: false,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handleBallPointerMove = (
    event: ReactPointerEvent<HTMLButtonElement>,
  ) => {
    const dragState = dragStateRef.current
    if (!dragState || dragState.pointerId !== event.pointerId) return

    const deltaX = event.clientX - dragState.startX
    const deltaY = event.clientY - dragState.startY
    if (Math.hypot(deltaX, deltaY) > 4) dragState.moved = true

    const currentViewport = {
      width: viewport.width || window.innerWidth,
      height: viewport.height || window.innerHeight,
    }
    setBallPosition(
      clampPosition(
        {
          x: dragState.originX + deltaX,
          y: dragState.originY + deltaY,
        },
        currentViewport,
      ),
    )
  }

  const handleBallPointerUp = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const dragState = dragStateRef.current
    if (!dragState || dragState.pointerId !== event.pointerId) return
    suppressClickRef.current = dragState.moved
    dragStateRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const handleBallClick = () => {
    if (suppressClickRef.current) {
      suppressClickRef.current = false
      return
    }
    setIsOpen((open) => !open)
  }

  return (
    <>
      {isOpen && (
        <>
          <button
            type="button"
            aria-label="关闭数字人对话"
            className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[2px]"
            onClick={() => setIsOpen(false)}
          />
          <aside
            aria-label="知识库数字人对话"
            className="fixed top-1/2 left-1/2 z-50 grid h-[min(760px,calc(100vh-32px))] w-[min(1180px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 grid-cols-1 grid-rows-[minmax(220px,42%)_minmax(0,1fr)] overflow-hidden border border-slate-300 bg-background shadow-2xl md:grid-cols-[minmax(340px,0.9fr)_minmax(440px,1.1fr)] md:grid-rows-1"
          >
            <section className="flex min-h-0 flex-col border-b bg-slate-950 text-white md:border-r md:border-b-0">
              <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                <div>
                  <div className="text-[11px] font-medium tracking-[0.18em] text-slate-400">
                    DIGITAL TUTOR
                  </div>
                  <h2 className="mt-1 text-base font-semibold">知识库数字人</h2>
                </div>
                <span className="flex items-center gap-2 text-xs text-slate-300">
                  <span
                    className={`size-2 ${
                      status === 'ready'
                        ? 'bg-emerald-400'
                        : status === 'speaking' ||
                            status === 'thinking' ||
                            status === 'listening'
                          ? 'animate-pulse bg-sky-400'
                          : status === 'error'
                            ? 'bg-red-400'
                            : 'bg-slate-500'
                    }`}
                  />
                  {statusCopy[status]}
                </span>
              </header>

              <div className="relative min-h-0 flex-1 overflow-hidden bg-neutral-950">
                <div ref={wrapperRef} className="absolute inset-0" />

                {status === 'connecting' && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-neutral-950 text-neutral-200">
                    <Loader2Icon className="size-7 animate-spin" />
                    <span className="text-sm">正在连接数字人…</span>
                  </div>
                )}

                {status === 'disabled' && (
                  <div className="absolute inset-0 flex items-center justify-center overflow-hidden bg-[#eef1f8]">
                    <img
                      src={digitalAvatarCover}
                      alt="数字人导师"
                      className="h-full w-full object-contain object-bottom"
                    />
                    <div className="absolute inset-x-5 bottom-5 border border-amber-300/40 bg-slate-950/85 p-4 text-center backdrop-blur-sm">
                      <CircleAlertIcon className="mx-auto size-5 text-amber-400" />
                      <div className="mt-2 text-sm font-medium">
                        数字人 SDK 尚未配置
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        请在根目录 .env 中填写 VITE_AVATAR_* 配置后重启前端。
                      </p>
                    </div>
                  </div>
                )}

                {needsInteraction && (
                  <div className="absolute inset-x-5 bottom-5 z-10 border border-white/15 bg-black/80 p-4 text-white backdrop-blur">
                    <p className="text-xs leading-5">
                      浏览器阻止了有声自动播放，请点击启用声音。
                    </p>
                    <Button
                      className="mt-3 w-full rounded-none"
                      size="sm"
                      onClick={() => void resumePlayback()}
                    >
                      <Volume2Icon className="size-4" />
                      启用声音
                    </Button>
                  </div>
                )}
              </div>

              <footer className="flex items-center justify-between border-t border-white/10 px-5 py-3 text-xs text-slate-400">
                <span>支持文字提问与语音交互</span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={
                      !isAvatarConfigured ||
                      status === 'connecting' ||
                      status === 'error'
                    }
                    className="rounded-none text-slate-300 hover:bg-white/10 hover:text-white"
                    onClick={() => void resumePlayback()}
                  >
                    <Volume2Icon className="size-4" />
                    {soundEnabled ? '声音已开启' : '开启声音'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={!isAvatarConfigured}
                    className="rounded-none text-slate-300 hover:bg-white/10 hover:text-white"
                    onClick={() => setInstanceKey((key) => key + 1)}
                  >
                    <RefreshCwIcon className="size-4" />
                    重新连接
                  </Button>
                </div>
              </footer>
            </section>

            <section className="flex min-h-0 flex-col bg-background">
              <header className="flex items-center justify-between border-b px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <SparklesIcon className="size-4 text-primary" />
                    <h2 className="text-base font-semibold">一对一咨询</h2>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    向数字人导师咨询课程知识或平台操作
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 rounded-none"
                  aria-label="关闭数字人对话"
                  onClick={() => setIsOpen(false)}
                >
                  <XIcon className="size-4" />
                </Button>
              </header>

              <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/70 px-6 py-5 dark:bg-slate-950/20">
                <div className="space-y-5">
                  {conversation.map((message) => (
                    <article
                      key={message.id}
                      className={`max-w-[86%] border px-4 py-3 shadow-sm ${
                        message.role === 'user'
                          ? 'ml-auto border-slate-800 bg-slate-900 text-white'
                          : 'border-slate-200 bg-background text-foreground'
                      }`}
                    >
                      <div
                        className={`mb-1 text-[11px] font-semibold tracking-wide ${
                          message.role === 'user'
                            ? 'text-slate-300'
                            : 'text-primary'
                        }`}
                      >
                        {message.role === 'user' ? '我' : '数字人导师'}
                      </div>
                      {message.role === 'assistant' ? (
                        <Response className="text-sm leading-6">
                          {message.content}
                        </Response>
                      ) : (
                        <p className="whitespace-pre-wrap text-sm leading-6">
                          {message.content}
                        </p>
                      )}
                    </article>
                  ))}

                  {isThinking && (
                    <div className="flex max-w-[86%] items-center gap-2 border border-slate-200 bg-background px-4 py-3 text-sm text-muted-foreground shadow-sm">
                      <Loader2Icon className="size-4 animate-spin text-primary" />
                      正在查询知识库并组织回答…
                    </div>
                  )}
                  <div ref={conversationEndRef} />
                </div>
              </div>

              {errorMessage && (
                <div className="border-t border-destructive/30 bg-destructive/5 px-5 py-3 text-xs leading-5 text-destructive">
                  {errorMessage}
                </div>
              )}

              <div className="border-t bg-background p-5">
                <Textarea
                  value={question}
                  maxLength={500}
                  rows={3}
                  disabled={unavailable || isRecording}
                  className="min-h-24 resize-none rounded-none border-slate-300 text-sm shadow-none focus-visible:ring-1"
                  placeholder="请输入您的问题，Enter 发送，Shift + Enter 换行…"
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void askQuestion()
                    }
                  }}
                />

                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-xs text-muted-foreground">
                    {question.length}/500
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant={isRecording ? 'destructive' : 'outline'}
                      size="sm"
                      disabled={unavailable || (isThinking && !isRecording)}
                      className="rounded-none"
                      onClick={() => void toggleRecording()}
                    >
                      {isRecording ? (
                        <SquareIcon className="size-4" />
                      ) : (
                        <MicIcon className="size-4" />
                      )}
                      {isRecording ? '结束提问' : '语音提问'}
                    </Button>
                    <Button
                      size="sm"
                      className="min-w-24 rounded-none"
                      disabled={
                        unavailable ||
                        !question.trim() ||
                        isThinking ||
                        isRecording
                      }
                      onClick={() => void askQuestion()}
                    >
                      <SendIcon className="size-4" />
                      发送问题
                    </Button>
                  </div>
                </div>
              </div>
            </section>
          </aside>
        </>
      )}

      <Button
        type="button"
        size="icon"
        aria-label={isOpen ? '关闭数字人对话' : '打开数字人对话'}
        aria-expanded={isOpen}
        title="数字人导师"
        onClick={handleBallClick}
        onPointerDown={handleBallPointerDown}
        onPointerMove={handleBallPointerMove}
        onPointerUp={handleBallPointerUp}
        onPointerCancel={handleBallPointerUp}
        style={
          ballPosition
            ? { left: ballPosition.x, top: ballPosition.y }
            : undefined
        }
        className={`fixed z-50 size-16 touch-none overflow-hidden rounded-full border-4 border-background p-0 shadow-xl select-none ${
          ballPosition ? '' : 'right-5 bottom-5 sm:right-7 sm:bottom-7'
        }`}
      >
        <img
          src={digitalAvatarCover}
          alt="数字人导师"
          draggable={false}
          className="size-full scale-150 object-cover object-top"
        />
        {isOpen && (
          <span className="absolute inset-0 flex items-center justify-center bg-black/45 text-white">
            <XIcon className="size-6" />
          </span>
        )}
        {!isOpen && isAvatarConfigured && (
          <span className="absolute top-0 right-0 size-3 rounded-full border-2 border-background bg-emerald-500" />
        )}
      </Button>
    </>
  )
}
