import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

type XfyunIatUrlDto = {
  url: string
  app_id: string
  expires_in_seconds: number
}

type StartXfyunIatOptions = {
  onTranscript: (text: string) => void
  onListeningChange?: (listening: boolean) => void
  onError?: (error: Error) => void
}

export type XfyunIatSession = {
  stop: () => void
}

const TARGET_SAMPLE_RATE = 16_000
const FRAME_BYTES = 1280

const fetchXfyunIatUrl = async (): Promise<XfyunIatUrlDto> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const headers: HeadersInit = {}
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const baseUrl = env.VITE_SERVER_URL ?? 'http://localhost:8000'
  const response = await fetch(`${baseUrl}/api/v1/speech/xfyun-iat-url`, {
    headers,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Failed to create XFYun speech session')
  }

  return response.json()
}

const bytesToBase64 = (bytes: Uint8Array) => {
  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  return btoa(binary)
}

const decodeBase64Utf8 = (value: string) => {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new TextDecoder().decode(bytes)
}

const resample = (
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate: number,
) => {
  if (inputSampleRate === outputSampleRate) {
    return input
  }

  const ratio = inputSampleRate / outputSampleRate
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)

  for (let index = 0; index < outputLength; index += 1) {
    const inputIndex = index * ratio
    const before = Math.floor(inputIndex)
    const after = Math.min(before + 1, input.length - 1)
    const weight = inputIndex - before
    output[index] = input[before] * (1 - weight) + input[after] * weight
  }

  return output
}

const floatToPcm16 = (input: Float32Array) => {
  const bytes = new Uint8Array(input.length * 2)
  const view = new DataView(bytes.buffer)

  for (let index = 0; index < input.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[index]))
    view.setInt16(
      index * 2,
      sample < 0 ? sample * 0x8000 : sample * 0x7fff,
      true,
    )
  }

  return bytes
}

const appendBytes = (left: Uint8Array, right: Uint8Array) => {
  const output = new Uint8Array(left.length + right.length)
  output.set(left, 0)
  output.set(right, left.length)
  return output
}

type XfyunResultText = {
  sn?: number
  pgs?: 'apd' | 'rpl'
  rg?: [number, number]
  ws?: Array<{
    cw?: Array<{
      w?: string
    }>
  }>
}

const getResultWords = (payload: XfyunResultText) =>
  (payload.ws ?? [])
    .flatMap((item) => item.cw ?? [])
    .map((item) => item.w ?? '')
    .join('')

export const startXfyunIat = async ({
  onTranscript,
  onListeningChange,
  onError,
}: StartXfyunIatOptions): Promise<XfyunIatSession> => {
  const connection = await fetchXfyunIatUrl()
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })
  const audioContext = new AudioContext()
  const source = audioContext.createMediaStreamSource(stream)
  const processor = audioContext.createScriptProcessor(4096, 1, 1)
  const socket = new WebSocket(connection.url)
  const resultBySequence = new Map<number, string>()

  let seq = 0
  let pending = new Uint8Array()
  let stopped = false
  let socketReady = false

  const cleanup = () => {
    if (stopped) return
    stopped = true
    onListeningChange?.(false)
    processor.disconnect()
    source.disconnect()
    stream.getTracks().forEach((track) => track.stop())
    void audioContext.close()
    if (
      socket.readyState === WebSocket.CONNECTING ||
      socket.readyState === WebSocket.OPEN
    ) {
      socket.close()
    }
  }

  const sendFrame = (audio: Uint8Array, status: 0 | 1 | 2) => {
    if (!socketReady || socket.readyState !== WebSocket.OPEN) {
      return
    }

    seq += 1
    const frame =
      status === 0
        ? {
            header: {
              app_id: connection.app_id,
              status,
            },
            parameter: {
              iat: {
                domain: 'slm',
                language: 'zh_cn',
                accent: 'mandarin',
                eos: 6000,
                dwa: 'wpgs',
                result: {
                  encoding: 'utf8',
                  compress: 'raw',
                  format: 'json',
                },
              },
            },
            payload: {
              audio: {
                encoding: 'raw',
                sample_rate: TARGET_SAMPLE_RATE,
                channels: 1,
                bit_depth: 16,
                seq,
                status,
                audio: bytesToBase64(audio),
              },
            },
          }
        : {
            header: {
              app_id: connection.app_id,
              status,
            },
            payload: {
              audio: {
                encoding: 'raw',
                sample_rate: TARGET_SAMPLE_RATE,
                channels: 1,
                bit_depth: 16,
                seq,
                status,
                audio: status === 2 ? '' : bytesToBase64(audio),
              },
            },
          }

    socket.send(JSON.stringify(frame))
  }

  const flushAudio = () => {
    while (pending.length >= FRAME_BYTES) {
      const frame = pending.slice(0, FRAME_BYTES)
      pending = pending.slice(FRAME_BYTES)
      sendFrame(frame, seq === 0 ? 0 : 1)
    }
  }

  socket.onopen = () => {
    socketReady = true
    onListeningChange?.(true)
  }

  socket.onerror = () => {
    const error = new Error('XFYun speech WebSocket connection failed')
    onError?.(error)
    cleanup()
  }

  socket.onclose = () => {
    cleanup()
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data as string)
      const code = data.header?.code
      if (typeof code === 'number' && code !== 0) {
        throw new Error(data.header?.message ?? `XFYun speech error ${code}`)
      }

      const encodedText = data.payload?.result?.text
      if (typeof encodedText === 'string' && encodedText) {
        const resultText = JSON.parse(decodeBase64Utf8(encodedText))
        const sn =
          typeof resultText.sn === 'number'
            ? resultText.sn
            : resultBySequence.size + 1
        const text = getResultWords(resultText)

        if (resultText.pgs === 'rpl' && Array.isArray(resultText.rg)) {
          const [start, end] = resultText.rg
          for (let index = start; index <= end; index += 1) {
            resultBySequence.delete(index)
          }
        }
        resultBySequence.set(sn, text)

        const transcript = Array.from(resultBySequence.entries())
          .sort(([left], [right]) => left - right)
          .map(([, value]) => value)
          .join('')
        onTranscript(transcript)
      }

      if (data.header?.status === 2) {
        cleanup()
      }
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error(String(error)))
    }
  }

  processor.onaudioprocess = (event) => {
    if (stopped) return
    const input = event.inputBuffer.getChannelData(0)
    const sampled = resample(input, audioContext.sampleRate, TARGET_SAMPLE_RATE)
    pending = appendBytes(pending, floatToPcm16(sampled))
    flushAudio()
  }

  source.connect(processor)
  processor.connect(audioContext.destination)

  return {
    stop: () => {
      if (stopped) return
      flushAudio()
      sendFrame(new Uint8Array(), 2)
      cleanup()
    },
  }
}
