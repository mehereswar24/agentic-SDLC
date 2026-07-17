import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  AgentStepView,
  ArtifactKind,
  ArtifactView,
  RunDetail,
  WsEvent,
} from "./types";
import { api, apiUrl } from "./api";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export type ConnectionState = "connecting" | "open" | "polling";

export interface RunActivity {
  node: string;
  message: string;
  agent?: string;
  stage?: string;
  ts: string;
}

function reduceEvent(prev: RunDetail, ev: WsEvent): RunDetail {
  const p = ev.payload;
  switch (ev.type) {
    case "run.started":
    case "run.resumed":
      return { ...prev, status: "running" };
    case "step.completed": {
      const step: AgentStepView = {
        id: String(p.id ?? ev.ts),
        node: String(p.node ?? ""),
        agent: p.agent != null ? String(p.agent) : null,
        input: {},
        output: (p as Record<string, unknown>) ?? {},
        error: null,
        latency_ms: (p.latency_ms as number) ?? null,
        tokens_in: (p.tokens_in as number) ?? null,
        tokens_out: (p.tokens_out as number) ?? null,
        created_at: ev.ts,
      };
      const exists = prev.steps.some(
        (s) => s.node === step.node && s.created_at === step.created_at,
      );
      return exists ? prev : { ...prev, steps: [...prev.steps, step] };
    }
    case "step.failed": {
      const step: AgentStepView = {
        id: String(p.id ?? ev.ts),
        node: String(p.node ?? ""),
        agent: null,
        input: {},
        output: {},
        error: String(p.error ?? "failed"),
        latency_ms: null,
        tokens_in: null,
        tokens_out: null,
        created_at: ev.ts,
      };
      return { ...prev, steps: [...prev.steps, step] };
    }
    case "run.awaiting_approval":
      return {
        ...prev,
        status: "awaiting_human",
        meta: {
          ...prev.meta,
          awaiting_stage: (p.next_stage as RunDetail["meta"]["awaiting_stage"]) ?? null,
          last_completed_stage:
            (p.completed_stage as RunDetail["meta"]["last_completed_stage"]) ?? null,
          ...(p.revision ? { pending_revision: null } : {}),
        },
      };
    case "run.completed":
      return { ...prev, status: "completed" };
    case "run.failed":
      return { ...prev, status: "failed", error: String(p.error ?? "failed") };
    case "run.cancelled":
      return { ...prev, status: "cancelled", error: String(p.reason ?? "cancelled") };
    default:
      return prev;
  }
}

/**
 * Live run state: one react-query cache entry (`["run", runId]`) fed primarily
 * by the backend WebSocket; a 3s poll takes over only while the socket is
 * down and the run isn't terminal. `activity` surfaces the latest
 * `step.progress` message (ephemeral — never cached or persisted).
 */
export function useRunLive(runId: string) {
  const qc = useQueryClient();
  const [wsOpen, setWsOpen] = useState(false);
  const [everConnected, setEverConnected] = useState(false);
  const [activity, setActivity] = useState<RunActivity | null>(null);
  // Mirrors wsOpen for the refetchInterval closure without re-creating the query.
  const wsOpenRef = useRef(false);

  const query = useQuery<RunDetail>({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (wsOpenRef.current) return false;
      if (data && TERMINAL.has(data.status)) return false;
      return 3000;
    },
  });

  useEffect(() => {
    const wsUrl = `${apiUrl.replace(/^http/, "ws")}/ws/runs/${runId}`;

    let ws: WebSocket | null = null;
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const markOpen = (open: boolean) => {
      wsOpenRef.current = open;
      setWsOpen(open);
      if (open) setEverConnected(true);
    };

    const mergeArtifact = async (kind: ArtifactKind, version: number) => {
      try {
        const art = await api.getArtifactVersion(runId, kind, version);
        qc.setQueryData<RunDetail>(["run", runId], (prev) => {
          if (!prev) return prev;
          const exists = prev.artifacts.some(
            (a) => a.kind === art.kind && a.version === art.version,
          );
          return exists
            ? prev
            : { ...prev, artifacts: [...prev.artifacts, art as ArtifactView] };
        });
      } catch {
        // Fall back to one authoritative refetch.
        qc.invalidateQueries({ queryKey: ["run", runId] });
      }
    };

    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        attempt = 0;
        markOpen(true);
      };

      ws.onmessage = (e) => {
        let msg: { type: string; run?: RunDetail; data?: WsEvent };
        try {
          msg = JSON.parse(e.data);
        } catch {
          return;
        }
        if (msg.type === "snapshot" && msg.run) {
          // Full replay on every (re)connect — dropped connections self-heal.
          qc.setQueryData<RunDetail>(["run", runId], msg.run);
          return;
        }
        if (msg.type !== "event" || !msg.data) return;
        const ev = msg.data;

        if (ev.type === "step.progress") {
          setActivity({
            node: String(ev.payload.node ?? ""),
            message: String(ev.payload.message ?? ""),
            agent: ev.payload.agent ? String(ev.payload.agent) : undefined,
            stage: ev.payload.stage ? String(ev.payload.stage) : undefined,
            ts: ev.ts,
          });
          return;
        }
        if (ev.type === "step.started") {
          setActivity(null);
        }
        if (TERMINAL.has(ev.type.replace("run.", "")) || ev.type === "run.awaiting_approval") {
          setActivity(null);
        }

        qc.setQueryData<RunDetail>(["run", runId], (prev) =>
          prev ? reduceEvent(prev, ev) : prev,
        );

        if (ev.type === "artifact.created") {
          const kind = ev.payload.kind as ArtifactKind;
          const version = (ev.payload.version as number) ?? 1;
          void mergeArtifact(kind, version);
        }
        if (ev.type === "run.awaiting_approval" || TERMINAL.has(ev.type.replace("run.", ""))) {
          // Rare, authoritative sync for meta (stage_index, feedback_history…).
          qc.invalidateQueries({ queryKey: ["run", runId] });
          qc.invalidateQueries({ queryKey: ["runs"] });
        }
      };

      const handleClose = (e?: CloseEvent) => {
        if (disposed) return;
        markOpen(false);
        const cached = qc.getQueryData<RunDetail>(["run", runId]);
        const isTerminal = cached ? TERMINAL.has(cached.status) : false;
        // Clean close (1000) or finished run: stay closed — polling stays off
        // for terminal runs and takes over otherwise.
        if (e?.code === 1000 || isTerminal) return;
        if (retryTimer) return;
        const delay = Math.min(1000 * 2 ** attempt, 15_000);
        attempt += 1;
        retryTimer = setTimeout(() => {
          retryTimer = null;
          connect();
        }, delay);
      };

      ws.onclose = handleClose;
      ws.onerror = () => {
        // onclose always follows onerror; reconnect logic lives there.
      };
    };

    connect();

    return () => {
      disposed = true;
      wsOpenRef.current = false;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [runId, qc]);

  const isTerminal = query.data ? TERMINAL.has(query.data.status) : false;
  const connection: ConnectionState = wsOpen
    ? "open"
    : everConnected || isTerminal
      ? "polling"
      : "connecting";

  return {
    run: query.data,
    isLoading: query.isLoading,
    error: query.error,
    connection,
    activity,
  };
}
