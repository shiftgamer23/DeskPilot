import { useCallback, useEffect, useRef, useState } from "react"

// Sarvam's REST speech-to-text endpoint is meant for clips under ~30s.
const MAX_RECORDING_MS = 28_000

export function useVoiceRecorder(onRecorded: (audio: Blob) => void) {
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const timerRef = useRef<number | null>(null)
  const onRecordedRef = useRef(onRecorded)

  useEffect(() => {
    onRecordedRef.current = onRecorded
  })

  const start = useCallback(async () => {
    setError(null)
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser can't record audio")
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        if (timerRef.current !== null) window.clearTimeout(timerRef.current)
        setRecording(false)
        onRecordedRef.current(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }))
      }
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
      timerRef.current = window.setTimeout(() => {
        if (recorder.state === "recording") recorder.stop()
      }, MAX_RECORDING_MS)
    } catch {
      setError("Microphone access was denied")
    }
  }, [])

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state === "recording") recorder.stop()
  }, [])

  return { recording, error, start, stop }
}
