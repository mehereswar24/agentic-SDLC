import { useQuery } from "@tanstack/react-query";
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
    max_revisions: input.maxRevisions,
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
    refetchInterval: 5000,
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
    refetchInterval: 10000,
  });
}
