import { useEffect, useState } from "react";
import type { ArtifactKind, RunDetail, WsEvent } from "./types";
import { apiUrl } from "./api";

// Keep only the most recent events; the UI derives everything it needs from
// the reduced `run` state, so an unbounded buffer would just leak memory on
// long runs.
const MAX_EVENTS = 200;

export function useRunStream(runId: string) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [connection, setConnection] = useState<"connecting" | "open" | "closed">("connecting");

  useEffect(() => {
    const wsUrl = `${apiUrl.replace(/^http/, "ws")}/ws/runs/${runId}`;

    let ws: WebSocket | null = null;
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const connect = () => {
      if (disposed) return;
      setConnection("connecting");
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        attempt = 0;
        setConnection("open");
      };

      ws.onmessage = (e) => {
        let msg: { type: string; run?: RunDetail; data?: WsEvent };
        try {
          msg = JSON.parse(e.data);
        } catch {
          return;
        }
        if (msg.type === "snapshot" && msg.run) {
          // The server replays a full snapshot on every (re)connect, so a
          // dropped connection self-heals without losing steps.
          setRun(msg.run);
          setEvents([]);
        } else if (msg.type === "event" && msg.data) {
          const ev = msg.data;
          setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), ev]);

          setRun((prev) => {
            if (!prev) return null;
            const p = ev.payload;
            switch (ev.type) {
              case "run.started":
                return { ...prev, status: "running" };
              case "step.started":
                return prev;
              case "step.completed": {
                const stepView = {
                  id: String(p.id ?? ev.ts),
                  node: String(p.node ?? ""),
                  agent: String(p.agent ?? ""),
                  input: (p.input as Record<string, unknown>) ?? {},
                  output: (p.output as Record<string, unknown>) ?? {},
                  error: null,
                  latency_ms: (p.latency_ms as number) ?? null,
                  tokens_in: (p.tokens_in as number) ?? null,
                  tokens_out: (p.tokens_out as number) ?? null,
                  created_at: ev.ts,
                };
                // Replace or append step
                const exists = prev.steps.some((s) => s.node === stepView.node && s.created_at === stepView.created_at);
                const steps = exists
                  ? prev.steps.map((s) => (s.node === stepView.node && s.created_at === stepView.created_at ? { ...s, ...stepView } : s))
                  : [...prev.steps, stepView];
                return { ...prev, steps };
              }
              case "step.failed": {
                const stepView = {
                  id: String(p.id ?? ev.ts),
                  node: String(p.node ?? ""),
                  agent: String(p.agent ?? ""),
                  input: {},
                  output: {},
                  error: String(p.error ?? "failed"),
                  latency_ms: null,
                  tokens_in: null,
                  tokens_out: null,
                  created_at: ev.ts,
                };
                return {
                  ...prev,
                  steps: [...prev.steps, stepView],
                };
              }
              case "artifact.created": {
                const artView = {
                  id: String(p.id ?? ev.ts),
                  kind: p.kind as ArtifactKind,
                  version: (p.version as number | undefined) ?? 1,
                  content: p.content ?? {},
                  created_at: ev.ts,
                };
                return {
                  ...prev,
                  artifacts: [...prev.artifacts, artView],
                };
              }
              case "run.completed":
                return { ...prev, status: "completed" };
              case "run.failed":
                return { ...prev, status: "failed", error: String(p.error ?? "failed") };
              case "run.cancelled":
                return { ...prev, status: "cancelled", error: String(p.reason ?? "cancelled") };
              default:
                return prev;
            }
          });
        }
      };

      const scheduleReconnect = () => {
        if (disposed || retryTimer) return;
        setConnection("closed");
        // Exponential backoff capped at 15s.
        const delay = Math.min(1000 * 2 ** attempt, 15_000);
        attempt += 1;
        retryTimer = setTimeout(() => {
          retryTimer = null;
          connect();
        }, delay);
      };

      ws.onclose = scheduleReconnect;
      ws.onerror = scheduleReconnect;
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [runId]);

  return { run, events, connection };
}
