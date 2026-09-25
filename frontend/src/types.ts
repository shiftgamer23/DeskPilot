export type Action = "auto_resolve" | "route" | "escalate"
export type RunStatus = "pending" | "running" | "done" | "error"

export interface GatedDecision {
  action: Action
  queue: string
  type: string
  priority: "low" | "medium" | "high"
  confidence: number
  justification: string
  cited_ticket_id: string | null
  llm_action: string
  llm_confidence: number
  gate_overridden: boolean
  gate_reason: string | null
  tools_called: string[]
  retrieval_top_score: number | null
  cached: boolean
}

// GET /tickets - list item (a trimmed view; see app/api/tickets.py::_run_summary)
export interface TicketSummary {
  run_id: string
  status: RunStatus
  subject: string | null
  body: string
  customer_id: string | null
  created_at: number
  action: Action | null
  queue: string | null
  confidence: number | null
  justification: string | null
  cached: boolean | null
}

// GET /tickets/{id} - full detail
export interface TicketDetail extends TicketSummary {
  result: GatedDecision | null
  error: string | null
}

export interface TicketAck {
  run_id: string
  status: RunStatus
}

// SSE event shapes - see app/agent/graph.py::_event_from_update and app/infra/run_store.py
export type StreamEvent =
  | { type: "tool_call"; tools: { name: string; args: Record<string, unknown> }[] }
  | { type: "tool_result"; results: { tool: string | null; content: unknown }[] }
  | { type: "nudge" }
  | { type: "agent_note"; content: string }
  | { type: "decision"; decision: GatedDecision }
  | { type: "end"; status: RunStatus; error?: string | null }
