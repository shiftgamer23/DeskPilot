import type { TicketAck, TicketDetail, TicketSummary } from "./types"

// Dev: "/api", proxied by Vite (see vite.config.ts) straight to the FastAPI backend on :8000.
// Prod: VITE_API_BASE_URL is the deployed backend's own origin (e.g. https://<app>.onrender.com) -
// there's no proxy in production and the backend's routes have no /api prefix of their own.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api"

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

async function errorDetail(res: Response, fallback: string): Promise<string> {
  const detail = await res.json().catch(() => ({}))
  return typeof detail.detail === "string" ? detail.detail : `${fallback} (${res.status})`
}

/** Sends the raw recorded audio as the request body (no multipart) and returns the English transcript. */
export async function transcribeAudio(audio: Blob): Promise<string> {
  const res = await fetch(`${BASE}/voice/transcribe`, {
    method: "POST",
    headers: { "Content-Type": audio.type || "audio/webm" },
    body: audio,
  })
  if (!res.ok) throw new Error(await errorDetail(res, "Transcription failed"))
  return (await res.json()).text
}

/** Audio of the agent telling the customer where their ticket was routed; only exists once the run is done. */
export async function fetchVoiceReply(runId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/tickets/${runId}/voice`)
  if (!res.ok) throw new Error(await errorDetail(res, "Voice reply failed"))
  return res.blob()
}
