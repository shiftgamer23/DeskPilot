import { LayoutGroup, motion } from "framer-motion"
import { AlertTriangle, Bot, CheckCircle2, Inbox, Sparkles, TrendingUp } from "lucide-react"
import { useEffect, useState } from "react"
import { listTickets, streamUrl } from "../api"
import { useSSE } from "../hooks/useSSE"
import { activityForTool } from "../lib/activity"
import type { StreamEvent, TicketSummary } from "../types"
import { Column } from "./Column"
import { TicketForm } from "./TicketForm"
import type { CardData } from "./TicketCard"

function summaryToCard(s: TicketSummary): CardData {
  return {
    runId: s.run_id,
    subject: s.subject,
    body: s.body,
    customerId: s.customer_id,
    status: s.status,
    action: s.action,
    queue: s.queue,
    confidence: s.confidence,
    justification: s.justification,
    cached: s.cached,
    activity: null,
  }
}

/** No visual output - keeps one SSE connection alive per in-flight ticket and reports events up to
 * Board, so Board can move the card into the right column the instant a decision arrives. */
function LiveSubscriber({ runId, onEvent }: { runId: string; onEvent: (runId: string, e: StreamEvent) => void }) {
  useSSE(streamUrl(runId), (event) => onEvent(runId, event))
  return null
}

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
}

function StatTile({ icon: Icon, label, value, accent }: { icon: typeof Bot; label: string; value: string; accent: string }) {
  return (
    <motion.div
      variants={fadeUp}
      className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 backdrop-blur-sm"
    >
      <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${accent}`}>
        <Icon size={16} />
      </div>
      <div>
        <div className="text-lg font-bold leading-none text-gray-100 tabular-nums">{value}</div>
        <div className="mt-1 text-[11px] text-gray-500">{label}</div>
      </div>
    </motion.div>
  )
}

function ColumnSkeleton() {
  return (
    <div className="flex w-80 shrink-0 flex-col gap-2 rounded-2xl border border-white/10 bg-white/[0.02] p-3">
      <div className="h-4 w-24 animate-pulse rounded bg-white/10" />
      <div className="mt-2 h-20 animate-pulse rounded-xl bg-white/5" />
      <div className="h-20 animate-pulse rounded-xl bg-white/5" />
    </div>
  )
}

export function Board() {
  const [tickets, setTickets] = useState<Record<string, CardData>>({})
  const [liveIds, setLiveIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listTickets()
      .then((summaries) => {
        setTickets(Object.fromEntries(summaries.map((s) => [s.run_id, summaryToCard(s)])))
      })
      .finally(() => setLoading(false))
  }, [])

  function handleSubmitted(runId: string, subject: string | null, body: string, customerId: string | null) {
    setTickets((prev) => ({
      ...prev,
      [runId]: {
        runId, subject, body, customerId, status: "pending",
        action: null, queue: null, confidence: null, justification: null, cached: null, activity: null,
      },
    }))
    setLiveIds((prev) => [...prev, runId])
  }

  function handleLiveEvent(runId: string, event: StreamEvent) {
    if (event.type === "tool_call") {
      const activity = activityForTool(event.tools[0]?.name ?? "")
      setTickets((prev) => (prev[runId] ? { ...prev, [runId]: { ...prev[runId], activity } } : prev))
    } else if (event.type === "decision") {
      const d = event.decision
      setTickets((prev) => ({
        ...prev,
        [runId]: {
          ...prev[runId], status: "running",
          action: d.action, queue: d.queue, confidence: d.confidence, justification: d.justification, cached: d.cached,
        },
      }))
    } else if (event.type === "end") {
      setTickets((prev) => ({ ...prev, [runId]: { ...prev[runId], status: event.status } }))
      setLiveIds((prev) => prev.filter((id) => id !== runId))
    }
  }

  const all = Object.values(tickets)
  const processing = all.filter((t) => t.status === "pending" || t.status === "running")
  const finished = all.filter((t) => t.status === "done")
  const errored = all.filter((t) => t.status === "error")
  const escalated = finished.filter((t) => t.action === "escalate")
  const autoResolved = finished.filter((t) => t.action === "auto_resolve")
  const queues = Array.from(
    new Set(finished.filter((t) => t.action !== "escalate" && t.queue).map((t) => t.queue as string)),
  ).sort()

  const escalationRate = finished.length ? Math.round((escalated.length / finished.length) * 100) : null
  const autoResolveRate = finished.length ? Math.round((autoResolved.length / finished.length) * 100) : null
  const avgConfidence = finished.length
    ? Math.round((finished.reduce((s, t) => s + (t.confidence ?? 0), 0) / finished.length) * 100)
    : null

  return (
    <div className="min-h-screen px-6 py-8">
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.08 } } }}
        className="mx-auto flex max-w-[1400px] flex-col gap-5"
      >
        <motion.div variants={fadeUp} className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/30">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-100">Ticket Triage Agent</h1>
            <p className="text-xs text-gray-500">Submit a ticket and watch it get investigated, decided, and routed live.</p>
          </div>
          <span className="ml-auto flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />
            Live
          </span>
        </motion.div>

        <motion.div variants={fadeUp} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile icon={Sparkles} label="Tickets triaged" value={String(finished.length)} accent="bg-indigo-500/15 text-indigo-300" />
          <StatTile
            icon={AlertTriangle}
            label="Escalation rate"
            value={escalationRate === null ? "—" : `${escalationRate}%`}
            accent="bg-amber-500/15 text-amber-300"
          />
          <StatTile
            icon={CheckCircle2}
            label="Auto-resolve rate"
            value={autoResolveRate === null ? "—" : `${autoResolveRate}%`}
            accent="bg-emerald-500/15 text-emerald-300"
          />
          <StatTile
            icon={TrendingUp}
            label="Avg. confidence"
            value={avgConfidence === null ? "—" : `${avgConfidence}%`}
            accent="bg-sky-500/15 text-sky-300"
          />
        </motion.div>

        <motion.div variants={fadeUp}>
          <TicketForm onSubmitted={handleSubmitted} />
        </motion.div>

        {liveIds.map((id) => (
          <LiveSubscriber key={id} runId={id} onEvent={handleLiveEvent} />
        ))}

        <motion.div variants={fadeUp} className="flex gap-3 overflow-x-auto pb-2">
          {loading ? (
            <>
              <ColumnSkeleton />
              <ColumnSkeleton />
              <ColumnSkeleton />
            </>
          ) : (
            <LayoutGroup>
              <Column title="Processing" tickets={processing} variant="processing" />
              <Column title="Needs Human Review" tickets={escalated} variant="review" />
              {queues.map((q) => (
                <Column key={q} title={q} tickets={finished.filter((t) => t.queue === q && t.action !== "escalate")} />
              ))}
              {errored.length > 0 && <Column title="Errors" tickets={errored} />}
            </LayoutGroup>
          )}
        </motion.div>

        {!loading && all.length === 0 && (
          <motion.div variants={fadeUp} className="flex flex-col items-center gap-2 py-16 text-gray-600">
            <Inbox size={28} className="opacity-40" />
            <p className="text-sm">No tickets submitted yet - try the form above.</p>
          </motion.div>
        )}
      </motion.div>
    </div>
  )
}
