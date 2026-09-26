import { AnimatePresence, motion } from "framer-motion"
import {
  AlertTriangle,
  ChevronDown,
  Loader2,
  MessageSquare,
  RefreshCw,
  Sparkles,
  User,
  Wand2,
  Wrench,
  Zap,
} from "lucide-react"
import { useState } from "react"
import { streamUrl } from "../api"
import { useSSE } from "../hooks/useSSE"
import { ACTION_META, confidenceTier } from "../lib/actionStyle"
import { DEFAULT_ACTIVITY } from "../lib/activity"
import type { Action, RunStatus, StreamEvent } from "../types"

export interface CardData {
  runId: string
  subject: string | null
  body: string
  customerId: string | null
  status: RunStatus
  action: Action | null
  queue: string | null
  confidence: number | null
  justification: string | null
  cached: boolean | null
  /** Human-friendly "what the agent is doing right now" phrase, live-updated from tool_call events while
   * status is pending/running. null before the first tool call, or for tickets loaded from GET /tickets
   * (already finished, never had a live phase in this browser session). */
  activity: string | null
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "..." : s
}

function fmtArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => `${k}=${truncate(JSON.stringify(v), 50)}`)
    .join(", ")
}

function TraceRow({ icon: Icon, accent, children }: { icon: typeof Wrench; accent: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 border-l-2 py-1 pl-2" style={{ borderColor: accent }}>
      <Icon size={13} className="mt-0.5 shrink-0" style={{ color: accent }} />
      <div className="min-w-0 text-gray-300">{children}</div>
    </div>
  )
}

function TraceEvent({ event }: { event: StreamEvent }) {
  if (event.type === "tool_call") {
    return (
      <>
        {event.tools.map((t, i) => (
          <TraceRow key={i} icon={Wrench} accent="#818cf8">
            <span className="text-indigo-300">{t.name}</span>
            <span className="text-gray-500">({fmtArgs(t.args)})</span>
          </TraceRow>
        ))}
      </>
    )
  }
  if (event.type === "tool_result") {
    return (
      <>
        {event.results.map((r, i) => (
          <TraceRow key={i} icon={Zap} accent="#38bdf8">
            <span className="text-sky-300">{r.tool}</span>{" "}
            <span className="text-gray-500">
              returned {Array.isArray(r.content) ? `${r.content.length} result(s)` : truncate(JSON.stringify(r.content), 100)}
            </span>
          </TraceRow>
        ))}
      </>
    )
  }
  if (event.type === "nudge")
    return (
      <TraceRow icon={RefreshCw} accent="#6b7280">
        <span className="italic text-gray-500">retrying - no tool call made</span>
      </TraceRow>
    )
  if (event.type === "agent_note")
    return (
      <TraceRow icon={MessageSquare} accent="#6b7280">
        {event.content}
      </TraceRow>
    )
  if (event.type === "decision") {
    const d = event.decision
    const meta = ACTION_META[d.action]
    return (
      <div className={`mt-1 rounded-lg border ${meta.border} ${meta.bg} p-2`}>
        <div className={`flex items-center gap-1.5 font-medium ${meta.text}`}>
          <meta.icon size={13} />
          {d.action} <span className="text-gray-500">· confidence {d.confidence.toFixed(2)}</span>
        </div>
        {d.gate_overridden && (
          <div className="mt-1 flex items-start gap-1.5 text-amber-400">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <span>
              Gate overrode the model's own "{d.llm_action}" call — {d.gate_reason}
            </span>
          </div>
        )}
      </div>
    )
  }
  return null
}

export function TicketCard({ data }: { data: CardData }) {
  const [expanded, setExpanded] = useState(false)
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [fetched, setFetched] = useState(false)

  useSSE(expanded && !fetched ? streamUrl(data.runId) : null, (event) => {
    setEvents((prev) => [...prev, event])
    if (event.type === "end") setFetched(true)
  })

  const isDeciding = data.status === "pending" || data.status === "running"
  const meta = data.action ? ACTION_META[data.action] : null
  const tier = data.confidence !== null ? confidenceTier(data.confidence) : null

  return (
    <motion.div
      layout
      layoutId={data.runId}
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ type: "spring", stiffness: 400, damping: 32 }}
      className="group rounded-xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-white/[0.01] p-3.5 text-sm shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-white/20"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-semibold leading-snug text-gray-100">{data.subject || truncate(data.body, 50)}</div>

        {isDeciding ? (
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-300">
            <Loader2 size={12} className="animate-spin" />
            Reasoning
          </span>
        ) : meta ? (
          <span className={`flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${meta.bg} ${meta.border} ${meta.text}`}>
            <meta.icon size={12} />
            {meta.label}
          </span>
        ) : (
          <span className="shrink-0 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300">
            error
          </span>
        )}
      </div>

      {data.customerId && (
        <div className="mt-1.5 flex items-center gap-1 text-xs text-gray-500">
          <User size={11} />
          {data.customerId}
        </div>
      )}

      {isDeciding && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-indigo-300/90">
          <Sparkles size={12} className="shrink-0 animate-pulse-dot" />
          <AnimatePresence mode="wait">
            <motion.span
              key={data.activity ?? DEFAULT_ACTIVITY}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              {data.activity ?? DEFAULT_ACTIVITY}
            </motion.span>
          </AnimatePresence>
        </div>
      )}

      {!isDeciding && data.confidence !== null && tier && (
        <div className="mt-2.5 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${data.confidence * 100}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className={`h-full rounded-full ${tier.fill}`}
            />
          </div>
          <span className={`shrink-0 text-xs font-medium tabular-nums ${tier.text}`}>
            {(data.confidence * 100).toFixed(0)}%
          </span>
          {data.cached && (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-violet-500/15 px-2 py-0.5 text-[11px] font-medium text-violet-300">
              <Zap size={10} />
              cached
            </span>
          )}
        </div>
      )}

      {!isDeciding && data.justification && (
        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-gray-400">{data.justification}</p>
      )}

      <button
        onClick={() => setExpanded((v) => !v)}
        className="mt-2.5 flex items-center gap-1 text-xs font-medium text-indigo-400 transition-colors hover:text-indigo-300"
      >
        <Wand2 size={12} />
        Reasoning trace
        <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={12} />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-0.5 rounded-lg border border-white/10 bg-black/30 p-2.5 font-mono text-[11px] leading-relaxed">
              {events.length === 0 && (
                <div className="flex items-center gap-1.5 text-gray-500">
                  <Loader2 size={11} className="animate-spin" />
                  Loading trace...
                </div>
              )}
              {events
                .filter((e) => e.type !== "end")
                .map((e, i) => (
                  <TraceEvent key={i} event={e} />
                ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
