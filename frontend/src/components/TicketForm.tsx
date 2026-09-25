import { Loader2, Send } from "lucide-react"
import { useState } from "react"
import { submitTicket } from "../api"

interface Props {
  onSubmitted: (runId: string, subject: string | null, body: string, customerId: string | null) => void
}

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

export function TicketForm({ onSubmitted }: Props) {
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [customerId, setCustomerId] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const ack = await submitTicket({
        subject: subject.trim() || null,
        body: body.trim(),
        customer_id: customerId.trim() || null,
      })
      onSubmitted(ack.run_id, subject.trim() || null, body.trim(), customerId.trim() || null)
      setSubject("")
      setBody("")
      setCustomerId("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit ticket")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-xl shadow-black/20 backdrop-blur-sm"
    >
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
      <div className="flex items-center justify-between pt-1">
        {error ? <span className="text-sm text-rose-400">{error}</span> : <span />}
        <button
          type="submit"
          disabled={submitting || !body.trim()}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-600/20 transition-all hover:bg-indigo-500 hover:shadow-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {submitting ? "Submitting..." : "Submit ticket"}
        </button>
      </div>
    </form>
  )
}
