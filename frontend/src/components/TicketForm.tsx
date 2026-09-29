import { AnimatePresence, motion } from "framer-motion"
import { ArrowRight, AudioLines, Keyboard, Loader2, Mic, Send, Square } from "lucide-react"
import { useState } from "react"
import { submitTicket, transcribeAudio } from "../api"
import { useVoiceRecorder } from "../hooks/useVoiceRecorder"

interface Props {
  onSubmitted: (
    runId: string,
    subject: string | null,
    body: string,
    customerId: string | null,
    viaVoice: boolean,
  ) => void
}

type Mode = "text" | "voice"

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{label}</span>
      {children}
    </label>
  )
}

const inputClass =
  "rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-gray-100 outline-none transition-colors placeholder:text-gray-600 focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/20"

const panelMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.18 },
}

export function TicketForm({ onSubmitted }: Props) {
  const [mode, setMode] = useState<Mode>("text")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [customerId, setCustomerId] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function submit(ticketBody: string, viaVoice: boolean) {
    setSubmitting(true)
    setError(null)
    try {
      const ack = await submitTicket({
        subject: subject.trim() || null,
        body: ticketBody,
        customer_id: customerId.trim() || null,
      })
      onSubmitted(ack.run_id, subject.trim() || null, ticketBody, customerId.trim() || null, viaVoice)
      setSubject("")
      setBody("")
      setCustomerId("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit ticket")
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (body.trim()) void submit(body.trim(), false)
  }

  // A spoken ticket goes through the same submit path as a typed one; the transcript becomes the ticket body.
  const recorder = useVoiceRecorder(async (audio) => {
    setTranscribing(true)
    setError(null)
    try {
      const text = await transcribeAudio(audio)
      setTranscript(text)
      await submit(text, true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed")
    } finally {
      setTranscribing(false)
    }
  })
  const busy = submitting || transcribing
  const shownError = error ?? recorder.error

  const voiceStatus = submitting
    ? "Sending your ticket to the agent..."
    : transcribing
      ? "Transcribing what you said..."
      : recorder.recording
        ? "Listening... tap to stop"
        : "Tap the mic and describe your issue"

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-xl shadow-black/20 backdrop-blur-sm">
      {mode === "text" ? (
        <button
          type="button"
          onClick={() => setMode("voice")}
          disabled={busy}
          className="group flex w-full items-center justify-between overflow-hidden rounded-xl bg-linear-to-r from-indigo-500 via-violet-500 to-fuchsia-500 px-5 py-3 text-left text-sm font-semibold text-white shadow-lg shadow-violet-500/30 transition-all hover:shadow-violet-500/50 hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="flex items-center gap-3">
            <span className="animate-pulse-dot flex h-9 w-9 items-center justify-center rounded-lg bg-white/20">
              <AudioLines size={18} />
            </span>
            <span className="flex flex-col leading-tight">
              <span>Switch to voice mode</span>
              <span className="text-xs font-normal text-white/75">Just say your issue - the agent talks back</span>
            </span>
          </span>
          <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
        </button>
      ) : (
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-sm font-semibold text-violet-300">
            <AudioLines size={16} />
            Voice mode
          </span>
          <button
            type="button"
            onClick={() => setMode("text")}
            disabled={busy || recorder.recording}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Keyboard size={14} />
            Switch to text mode
          </button>
        </div>
      )}

      <AnimatePresence mode="wait" initial={false}>
        {mode === "text" ? (
          <motion.form key="text" {...panelMotion} onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_220px]">
              <Field label="Subject">
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Optional - e.g. Billing question"
                  className={inputClass}
                />
              </Field>
              <Field label="Customer ID">
                <input
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  placeholder="Optional - e.g. CUST-0001"
                  className={inputClass}
                />
              </Field>
            </div>
            <Field label="Ticket body">
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Describe the issue..."
                rows={3}
                required
                className={`${inputClass} resize-y`}
              />
            </Field>
            <div className="flex items-center justify-between gap-3 pt-1">
              {shownError ? <span className="text-sm text-rose-400">{shownError}</span> : <span />}
              <button
                type="submit"
                disabled={busy || !body.trim()}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-600/20 transition-all hover:bg-indigo-500 hover:shadow-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                {submitting ? "Submitting..." : "Submit ticket"}
              </button>
            </div>
          </motion.form>
        ) : (
          <motion.div key="voice" {...panelMotion} className="flex flex-col items-center gap-3 py-1">
            <div className="w-full sm:w-[220px] sm:self-start">
              <Field label="Customer ID">
                <input
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  placeholder="Optional - e.g. CUST-0001"
                  disabled={busy || recorder.recording}
                  className={inputClass}
                />
              </Field>
            </div>

            <div className="relative flex h-28 w-28 items-center justify-center">
              {recorder.recording && <span className="absolute inset-2 animate-ping rounded-full bg-rose-500/30" />}
              <button
                type="button"
                onClick={recorder.recording ? recorder.stop : recorder.start}
                disabled={busy}
                aria-label={recorder.recording ? "Stop recording" : "Start recording"}
                className={`relative flex h-20 w-20 items-center justify-center rounded-full text-white shadow-xl transition-all hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100 ${
                  recorder.recording
                    ? "bg-rose-500 shadow-rose-500/40"
                    : "bg-linear-to-br from-indigo-500 via-violet-500 to-fuchsia-500 shadow-violet-500/40"
                }`}
              >
                {busy ? (
                  <Loader2 size={30} className="animate-spin" />
                ) : recorder.recording ? (
                  <Square size={24} className="fill-current" />
                ) : (
                  <Mic size={30} />
                )}
              </button>
            </div>

            <p className="relative text-sm font-medium text-gray-200">{voiceStatus}</p>
            {shownError && <p className="text-sm text-rose-400">{shownError}</p>}
            {transcript && !shownError && (
              <p className="max-w-xl text-center text-xs italic text-gray-400">You said: "{transcript}"</p>
            )}
            <p className="text-[11px] text-gray-600">
              Your ticket is submitted automatically, and the routing decision is read back to you.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
