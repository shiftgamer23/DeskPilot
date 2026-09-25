/** Maps internal tool/event names to a human-friendly "what the agent is doing right now" phrase, for the
 * live status line on a ticket card. The raw names still appear in the detailed reasoning-trace panel. */
export function activityForTool(toolName: string): string {
  switch (toolName) {
    case "search_past_tickets":
      return "Searching for similar past incidents..."
    case "get_customer_context":
      return "Analyzing customer history..."
    case "submit_decision":
      return "Finalizing the decision..."
    default:
      return "Investigating the ticket..."
  }
}

export const DEFAULT_ACTIVITY = "Reading the ticket..."
