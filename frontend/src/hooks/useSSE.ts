import { useEffect, useRef } from "react"
import type { StreamEvent } from "../types"

/** Subscribes to an SSE endpoint while `url` is non-null. Works identically for a run that's still live
 * (events arrive over time) and one that already finished (the backend replays its history, then sends
 * `end`, immediately - see GET /tickets/{id}/stream's replay path in app/api/tickets.py). Auto-closes on
 * an `end` event or unmount. */
export function useSSE(url: string | null, onEvent: (event: StreamEvent) => void) {
  const cbRef = useRef(onEvent)
  cbRef.current = onEvent

  useEffect(() => {
    if (!url) return
    const es = new EventSource(url)
    es.onmessage = (e) => {
      const data = JSON.parse(e.data) as StreamEvent
      cbRef.current(data)
      if (data.type === "end") es.close()
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [url])
}
