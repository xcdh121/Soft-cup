import {
  CircleAlertIcon,
  Loader2Icon,
  MicIcon,
  RefreshCwIcon,
  SendIcon,
  SparklesIcon,
  SquareIcon,
  Volume2Icon,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
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
  const [instanceKey, setInstanceKey] = useState(0)
  const [question, setQuestion] = useState('')
  const [lastQuestion, setLastQuestion] = useState('')
  const [answerText, setAnswerText] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [status, setStatus] = useState<AvatarStatus>(
    isAvatarConfigured ? 'connecting' : 'disabled',
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [needsInteraction, setNeedsInteraction] = useState(false)

  useEffect(() => {
    if (!isAvatarConfigured || !wrapperRef.current) return

    let disposed = false
    const avatar = new AvatarPlatform()
    avatarRef.current = avatar
    isReadyRef.current = false
    setStatus('connecting')
    setErrorMessage(null)
    setNeedsInteraction(false)

    avatar
      .on(SDKEvents.nlp, (event: unknown) => {
        if (disposed) return
        const text = getAvatarEventText(event)
        if (text) setAnswerText(text)
        if (getAvatarEventStatus(event) === 2) setIsThinking(false)
      })
      .on(SDKEvents.asr, (event: unknown) => {
        if (disposed) return
        const text = getAvatarEventText(event)
        if (text) setLastQuestion(text)
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
    player.on(PlayerEvents.playNotAllowed, () => {
      if (!disposed) setNeedsInteraction(true)
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
  }, [instanceKey])

  const askQuestion = useCallback(async () => {
    const text = question.trim()
    const avatar = avatarRef.current
    if (!text || !avatar || !isReadyRef.current || isRecordingRef.current) {
      return
    }

    try {
      if (isSpeakingRef.current) await avatar.interrupt()
      setLastQuestion(text)
      setAnswerText('')
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
  }, [question])

  const toggleRecording = useCallback(async () => {
    const avatar = avatarRef.current
    const recorder = recorderRef.current
    if (!avatar || !recorder || !isReadyRef.current) return

    try {
      if (isRecordingRef.current) {
        await recorder.stopRecord()
        isRecordingRef.current = false
        setIsRecording(false)
        setIsThinking(true)
        setStatus('thinking')
        return
      }

      if (isSpeakingRef.current) await avatar.interrupt()
      setLastQuestion('正在识别语音…')
      setAnswerText('')
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
  }, [])

  const resumePlayback = async () => {
    try {
      await avatarRef.current?.player?.resume()
      setNeedsInteraction(false)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  const unavailable =
    !isAvatarConfigured || status === 'connecting' || status === 'error'

  return (
    <aside className="hidden min-h-0 bg-background xl:flex xl:flex-col">
      <div className="border-b px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SparklesIcon className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">知识库数字人</h2>
          </div>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={`size-1.5 rounded-full ${
                status === 'ready'
                  ? 'bg-emerald-500'
                  : status === 'speaking' ||
                      status === 'thinking' ||
                      status === 'listening'
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
          可询问数据结构知识或平台操作，数字人会理解问题并回答讲解。
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
        <div className="relative min-h-64 flex-[4] overflow-hidden rounded-xl border bg-neutral-950 shadow-sm">
          <div ref={wrapperRef} className="size-full" />

          {status === 'connecting' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-neutral-950 text-neutral-200">
              <Loader2Icon className="size-6 animate-spin" />
              <span className="text-sm">正在连接数字人…</span>
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

        <div className="max-h-40 min-h-20 overflow-y-auto rounded-lg border bg-muted/30 p-3 text-xs leading-5">
          {!lastQuestion && !isThinking && !answerText && (
            <div className="text-muted-foreground">
              <p>你可以这样问：</p>
              <p>“什么是二叉树？” 或 “如何在平台上传学习文档？”</p>
            </div>
          )}
          {lastQuestion && (
            <p>
              <span className="font-medium text-foreground">你问：</span>
              <span className="text-muted-foreground">{lastQuestion}</span>
            </p>
          )}
          {isThinking && (
            <p className="mt-1 flex items-center gap-1.5 text-primary">
              <Loader2Icon className="size-3.5 animate-spin" />
              正在查询知识库并组织讲解…
            </p>
          )}
          {answerText && (
            <p className="mt-1 whitespace-pre-wrap">
              <span className="font-medium text-primary">数字人：</span>
              <span>{answerText}</span>
            </p>
          )}
        </div>

        {errorMessage && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
            {errorMessage}
          </div>
        )}

        <Textarea
          value={question}
          maxLength={500}
          rows={2}
          disabled={unavailable || isRecording}
          className="min-h-16 resize-none text-sm"
          placeholder="向数字人提问数据结构或平台操作…"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void askQuestion()
            }
          }}
        />

        <div className="grid grid-cols-2 gap-2">
          <Button
            size="sm"
            disabled={
              unavailable || !question.trim() || isThinking || isRecording
            }
            onClick={() => void askQuestion()}
          >
            <SendIcon className="size-4" />
            提问
          </Button>
          <Button
            variant={isRecording ? 'destructive' : 'outline'}
            size="sm"
            disabled={unavailable || (isThinking && !isRecording)}
            onClick={() => void toggleRecording()}
          >
            {isRecording ? (
              <SquareIcon className="size-4" />
            ) : (
              <MicIcon className="size-4" />
            )}
            {isRecording ? '结束提问' : '语音提问'}
          </Button>
        </div>

        <Button
          variant="ghost"
          size="sm"
          disabled={!isAvatarConfigured}
          onClick={() => setInstanceKey((key) => key + 1)}
        >
          <RefreshCwIcon className="size-4" />
          重新连接
        </Button>
      </div>
    </aside>
  )
}
