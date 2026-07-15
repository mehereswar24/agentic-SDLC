import { createServerFn } from "@tanstack/react-start";
import {
  runPlan,
  runDesign,
  runSprintPlan,
  runBuild,
  runTest,
  GATED_STAGES,
} from "./agents.server";
import type {
  StageKey,
  RunMeta,
  PRD,
  SystemDesign,
  CodeBundle,
} from "./types";
import { STAGES, ARTIFACT_FOR_STAGE } from "./types";

const STAGE_ORDER: StageKey[] = STAGES.map((s) => s.key);

async function getAdmin() {
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
  return supabaseAdmin;
}

async function loadArtifact<T>(runId: string, kind: string): Promise<T | null> {
  const admin = await getAdmin();
  const { data } = await admin
    .from("artifacts")
    .select("content")
    .eq("run_id", runId)
    .eq("kind", kind)
    .order("version", { ascending: false })
    .limit(1)
    .maybeSingle();
  return (data?.content as T) ?? null;
}

// Advance the run by exactly one stage. Client calls repeatedly while status is "running".
export const advanceRun = createServerFn({ method: "POST" })
  .inputValidator((data: { runId: string }) => data)
  .handler(async ({ data }) => {
    const admin = await getAdmin();
    const { runId } = data;

    const { data: run, error: runErr } = await admin
      .from("runs")
      .select("*")
      .eq("id", runId)
      .single();
    if (runErr || !run) throw new Error("Run not found");

    const meta = run.meta as unknown as RunMeta;

    if (run.status === "awaiting_human" || run.status === "completed" || run.status === "failed") {
      return { status: run.status };
    }

    const stageIndex = (meta.stage_index as number | undefined) ?? 0;
    if (stageIndex >= STAGE_ORDER.length) {
      await admin.from("runs").update({ status: "completed" }).eq("id", runId);
      return { status: "completed" };
    }

    const stage = STAGE_ORDER[stageIndex];
    const feedback = meta.feedback?.[stage];

    await admin.from("runs").update({ status: "running", error: null }).eq("id", runId);

    try {
      let result;
      if (stage === "plan") {
        result = await runPlan(run.prompt, meta.max_revisions ?? 2, feedback);
      } else if (stage === "design") {
        const prd = await loadArtifact<PRD>(runId, "prd");
        if (!prd) throw new Error("Missing PRD");
        result = await runDesign(prd, feedback);
      } else if (stage === "sprint_plan") {
        const prd = await loadArtifact<PRD>(runId, "prd");
        const design = await loadArtifact<SystemDesign>(runId, "system_design");
        if (!prd || !design) throw new Error("Missing PRD or design");
        result = await runSprintPlan(prd, design, feedback);
      } else if (stage === "build") {
        const prd = await loadArtifact<PRD>(runId, "prd");
        const design = await loadArtifact<SystemDesign>(runId, "system_design");
        if (!prd || !design) throw new Error("Missing PRD or design");
        result = await runBuild(prd, design);
      } else {
        const bundle = await loadArtifact<CodeBundle>(runId, "code");
        if (!bundle) throw new Error("Missing code bundle");
        result = await runTest(bundle);
      }

      // Persist agent steps.
      if (result.steps.length) {
        await admin.from("agent_steps").insert(
          result.steps.map((s) => ({
            run_id: runId,
            node: s.node,
            agent: s.agent,
            input: s.input,
            output: s.output,
            latency_ms: s.latency_ms,
            tokens_in: s.tokens_in,
            tokens_out: s.tokens_out,
          })) as never,
        );
      }

      // Persist artifact.
      await admin.from("artifacts").insert({
        run_id: runId,
        kind: ARTIFACT_FOR_STAGE[stage],
        version: result.version,
        content: result.artifact as never,
      });

      const nextIndex = (stageIndex as number) + 1;
      const isGated = GATED_STAGES.includes(stage);
      const isLast = nextIndex >= STAGE_ORDER.length;

      const newMeta: RunMeta = {
        ...meta,
        stage_index: nextIndex,
        last_completed_stage: stage,
        awaiting_stage: isGated && !meta.auto_approve && !isLast ? stage : null,
      };

      let newStatus: string;
      if (isLast) newStatus = "completed";
      else if (isGated && !meta.auto_approve) newStatus = "awaiting_human";
      else newStatus = "running";

      await admin
        .from("runs")
        .update({ status: newStatus, meta: newMeta as never })
        .eq("id", runId);

      return { status: newStatus, stage };
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      await admin
        .from("agent_steps")
        .insert({ run_id: runId, node: stage, agent: "system", error: message });
      await admin.from("runs").update({ status: "failed", error: message }).eq("id", runId);
      return { status: "failed", error: message };
    }
  });

// Approve the current gate and resume.
export const approveGate = createServerFn({ method: "POST" })
  .inputValidator((data: { runId: string; feedback?: string }) => data)
  .handler(async ({ data }) => {
    const admin = await getAdmin();
    const { data: run } = await admin.from("runs").select("*").eq("id", data.runId).single();
    if (!run) throw new Error("Run not found");
    const meta = run.meta as unknown as RunMeta;

    const nextStage = STAGE_ORDER[(meta.stage_index as number | undefined) ?? 0];
    const feedbackMap = { ...(meta.feedback ?? {}) };
    if (data.feedback && data.feedback.trim() && nextStage) {
      feedbackMap[nextStage as string] = data.feedback.trim();
    }

    const newMeta: RunMeta = { ...meta, awaiting_stage: null, feedback: feedbackMap };
    await admin
      .from("runs")
      .update({ status: "running", meta: newMeta as never })
      .eq("id", data.runId);
    return { ok: true };
  });

// Reject and terminate the run.
export const rejectRun = createServerFn({ method: "POST" })
  .inputValidator((data: { runId: string; feedback?: string }) => data)
  .handler(async ({ data }) => {
    const admin = await getAdmin();
    const reason = data.feedback?.trim()
      ? `Rejected by reviewer: ${data.feedback.trim()}`
      : "Rejected by reviewer.";
    await admin
      .from("runs")
      .update({ status: "failed", error: reason })
      .eq("id", data.runId);
    return { ok: true };
  });
