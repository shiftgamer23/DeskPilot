import { AlertTriangle, ArrowRightCircle, CheckCircle2, type LucideIcon } from "lucide-react"
import type { Action } from "../types"

export const ACTION_META: Record<Action, { label: string; icon: LucideIcon; text: string; bg: string; border: string }> = {
  auto_resolve: {
    label: "Auto-resolved",
    icon: CheckCircle2,
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  route: {
    label: "Routed",
    icon: ArrowRightCircle,
    text: "text-sky-300",
    bg: "bg-sky-500/10",
    border: "border-sky-500/30",
  },
  escalate: {
    label: "Escalated",
    icon: AlertTriangle,
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
}

export function confidenceTier(c: number): { fill: string; text: string } {
  if (c >= 0.8) return { fill: "bg-emerald-400", text: "text-emerald-300" }
  if (c >= 0.5) return { fill: "bg-amber-400", text: "text-amber-300" }
  return { fill: "bg-rose-400", text: "text-rose-300" }
}
