import type { TicketAck, TicketDetail, TicketSummary } from "./types"

// Proxied by Vite in dev (see vite.config.ts) straight to the FastAPI backend on :8000.
const BASE = "/api"

export interface SubmitTicketInput {
  subject?: string | null
  body: string
  customer_id?: string | null
  provider?: string | null
}

export async function submitTicket(input: SubmitTicketInput): Promise<TicketAck> {
  const res = await fetch(`${BASE}/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(typeof detail.detail === "string" ? detail.detail : `Request failed (${res.status})`)
  }
  return res.json()
}

export async function listTickets(limit = 200): Promise<TicketSummary[]> {
  const res = await fetch(`${BASE}/tickets?limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to list tickets (${res.status})`)
  return res.json()
}

export async function getTicket(runId: string): Promise<TicketDetail> {
  const res = await fetch(`${BASE}/tickets/${runId}`)
  if (!res.ok) throw new Error(`Failed to fetch ticket (${res.status})`)
  return res.json()
}

export function streamUrl(runId: string): string {
  return `${BASE}/tickets/${runId}/stream`
}
