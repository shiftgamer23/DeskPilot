import { AnimatePresence } from "framer-motion"
import { AlertTriangle, Inbox, Loader2, type LucideIcon } from "lucide-react"
import { TicketCard, type CardData } from "./TicketCard"

interface Props {
  title: string
  tickets: CardData[]
  variant?: "default" | "review" | "processing"
}

const VARIANT: Record<NonNullable<Props["variant"]>, { icon: LucideIcon; border: string; glow: string; title: string }> = {
  default: { icon: Inbox, border: "border-white/10", glow: "", title: "text-gray-200" },
  review: {
    icon: AlertTriangle,
    border: "border-amber-500/30",
    glow: "shadow-[0_0_24px_-8px_rgba(245,158,11,0.35)]",
    title: "text-amber-300",
  },
  processing: { icon: Loader2, border: "border-white/10", glow: "", title: "text-gray-200" },
}

export function Column({ title, tickets, variant = "default" }: Props) {
  const v = VARIANT[variant]
  return (
    <div
      className={`flex w-80 shrink-0 flex-col gap-2 rounded-2xl border ${v.border} ${v.glow} bg-white/[0.02] p-3 backdrop-blur-sm`}
    >
      <div className="flex items-center justify-between px-1 py-1">
        <div className="flex items-center gap-2">
          <v.icon size={14} className={variant === "processing" && tickets.length > 0 ? `${v.title} animate-spin` : v.title} />
          <h3 className={`text-sm font-semibold ${v.title}`}>{title}</h3>
        </div>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs font-medium text-gray-400 tabular-nums">
          {tickets.length}
        </span>
      </div>
      <div className="flex max-h-[65vh] min-h-[100px] flex-col gap-2 overflow-y-auto pr-1">
        <AnimatePresence mode="popLayout">
          {tickets.map((t) => (
            <TicketCard key={t.runId} data={t} />
          ))}
        </AnimatePresence>
        {tickets.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8 text-gray-600">
            <v.icon size={20} className="opacity-40" />
            <p className="text-xs">No tickets yet</p>
          </div>
        )}
      </div>
    </div>
  )
}
