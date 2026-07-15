import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export interface CreateRunInput {
  prompt: string;
  autoApprove: boolean;
  maxRevisions: number;
}

export async function createRun(input: CreateRunInput): Promise<string> {
  const res = await api.createRun({ 
    prompt: input.prompt,
    auto_approve: input.autoApprove,
    max_revisions: input.maxRevisions
  });
  return res.id;
}

export async function deleteRun(id: string): Promise<void> {
  await api.deleteRun(id);
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: async () => {
      const res = await api.listRuns(50);
      return res.runs;
    },
    refetchInterval: 3000,
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      return ["pending", "running", "awaiting_human"].includes(data.status) ? 2000 : false;
    },
  });
}

export function useSteps(runId: string) {
  return useQuery({
    queryKey: ["steps", runId],
    queryFn: async () => {
      const run = await api.getRun(runId);
      return run.steps || [];
    },
    refetchInterval: 2000,
  });
}

export function useArtifacts(runId: string) {
  return useQuery({
    queryKey: ["artifacts", runId],
    queryFn: async () => {
      const run = await api.getRun(runId);
      return run.artifacts || [];
    },
    refetchInterval: 2000,
  });
}

export interface Stats {
  totalRuns: number;
  byStatus: Record<string, number>;
  totalSteps: number;
  totalTokens: number;
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: async () => {
      const s = await api.stats();
      return {
        totalRuns: s.total_runs,
        byStatus: s.by_status,
        totalSteps: s.agent_steps,
        totalTokens: s.tokens_in_total + s.tokens_out_total,
      } as Stats;
    },
    refetchInterval: 5000,
  });
}

export function useRunRealtime(runId: string) {
  // React query refetchInterval handles polling automatically now.
  const qc = useQueryClient();
  useEffect(() => {
    // Optionally trigger an immediate refetch when mounting
    qc.invalidateQueries({ queryKey: ["run", runId] });
  }, [runId, qc]);
}

export function useRunsRealtime() {
  // Handled by refetchInterval
}
