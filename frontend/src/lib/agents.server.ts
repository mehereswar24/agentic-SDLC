// Agent prompt builders + execution. Server-only.
import { callModel, parseJson, type ChatMessage } from "./ai-gateway.server";
import type {
  PRD,
  SystemDesign,
  SprintPlan,
  CodeBundle,
  TestSuite,
  Critique,
  StageKey,
} from "./types";

interface StepLog {
  node: string;
  agent: string;
  input: unknown;
  output: unknown;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
}

export interface StageRunResult {
  artifact: unknown;
  steps: StepLog[];
  version: number;
}

const MODEL = "google/gemini-3-flash-preview";

async function timed(messages: ChatMessage[], json = true, provider: "local" | "gemini" = "gemini") {
  const start = Date.now();
  const res = await callModel(messages, { json, provider, model: provider === "gemini" ? MODEL : undefined });
  return { ...res, latency_ms: Date.now() - start };
}

function feedbackNote(feedback?: string): string {
  return feedback && feedback.trim()
    ? `\n\nThe human reviewer left this feedback to incorporate: "${feedback.trim()}"`
    : "";
}

// ---------- Stage 1: Plan (draft -> critique -> revise loop) ----------
export async function runPlan(
  prompt: string,
  maxRevisions: number,
  feedback?: string,
): Promise<StageRunResult> {
  const steps: StepLog[] = [];

  const prdInstruction = `Return ONLY valid JSON matching this exact shape:
{
  "title": string,
  "summary": string,
  "problem_statement": string,
  "goals": string[],
  "non_goals": string[],
  "personas": [{ "name": string, "description": string }],
  "user_stories": [{ "id": "US-1", "as_a": string, "i_want": string, "so_that": string, "acceptance_criteria": string[] }],
  "functional_requirements": string[],
  "non_functional_requirements": string[],
  "constraints": string[],
  "risks": string[],
  "success_metrics": string[]
}
Provide 4-8 user stories with sequential ids US-1, US-2, ...`;

  // Draft
  const draft = await timed([
    {
      role: "system",
      content:
        "You are PlannerAgent, an expert product manager. You write precise, comprehensive PRDs.",
    },
    {
      role: "user",
      content: `Write a Product Requirements Document for this brief:\n\n"${prompt}"${feedbackNote(feedback)}\n\n${prdInstruction}`,
    },
  ], true, "local");
  let prd = parseJson<PRD>(draft.content);
  steps.push({
    node: "draft",
    agent: "planner",
    input: { prompt },
    output: prd,
    latency_ms: draft.latency_ms,
    tokens_in: draft.tokensIn,
    tokens_out: draft.tokensOut,
  });

  const threshold = 8;
  for (let i = 0; i < maxRevisions; i++) {
    const critiqueRes = await timed([
      {
        role: "system",
        content:
          "You are a critical senior product reviewer. Score PRDs from 1-10 and give actionable feedback.",
      },
      {
        role: "user",
        content: `Critique this PRD. Return ONLY JSON: { "score": number (1-10), "strengths": string[], "weaknesses": string[], "suggestions": string[] }\n\nPRD:\n${JSON.stringify(prd)}`,
      },
    ], true, "local");
    const critique = parseJson<Critique>(critiqueRes.content);
    steps.push({
      node: "critique",
      agent: "planner",
      input: { version: i + 1 },
      output: critique,
      latency_ms: critiqueRes.latency_ms,
      tokens_in: critiqueRes.tokensIn,
      tokens_out: critiqueRes.tokensOut,
    });

    if ((critique.score ?? 0) >= threshold) break;

    const reviseRes = await timed([
      {
        role: "system",
        content: "You are PlannerAgent. Revise the PRD to address the critique.",
      },
      {
        role: "user",
        content: `Revise this PRD addressing the critique.\n\nCritique:\n${JSON.stringify(critique)}\n\nCurrent PRD:\n${JSON.stringify(prd)}\n\n${prdInstruction}`,
      },
    ], true, "local");
    prd = parseJson<PRD>(reviseRes.content);
    steps.push({
      node: "revise",
      agent: "planner",
      input: { revision: i + 1 },
      output: prd,
      latency_ms: reviseRes.latency_ms,
      tokens_in: reviseRes.tokensIn,
      tokens_out: reviseRes.tokensOut,
    });
  }

  return { artifact: prd, steps, version: 1 };
}

// ---------- Stage 2: Design ----------
export async function runDesign(prd: PRD, feedback?: string): Promise<StageRunResult> {
  const res = await timed([
    {
      role: "system",
      content:
        "You are DesignerAgent, a pragmatic software architect. You produce lightweight, sensible system designs.",
    },
    {
      role: "user",
      content: `Given this PRD, produce a system design.${feedbackNote(feedback)}\n\nReturn ONLY JSON:
{
  "overview": string,
  "components": [{ "name": string, "technology": string, "responsibility": string }],
  "data_models": [{ "entity": string, "purpose": string, "key_fields": string[] }],
  "integration_points": string[]
}\n\nPRD:\n${JSON.stringify(prd)}`,
    },
  ], true, "local");
  const design = parseJson<SystemDesign>(res.content);
  return {
    artifact: design,
    version: 1,
    steps: [
      {
        node: "design",
        agent: "designer",
        input: { prd_title: prd.title },
        output: design,
        latency_ms: res.latency_ms,
        tokens_in: res.tokensIn,
        tokens_out: res.tokensOut,
      },
    ],
  };
}

// ---------- Stage 3: Sprint Plan ----------
export async function runSprintPlan(
  prd: PRD,
  design: SystemDesign,
  feedback?: string,
): Promise<StageRunResult> {
  const res = await timed([
    {
      role: "system",
      content:
        "You are SprintPlannerAgent, an agile delivery lead. You break work into well-scoped sprints.",
    },
    {
      role: "user",
      content: `Group the user stories into 2-4 agile sprints with task breakdowns.${feedbackNote(feedback)}\n\nReturn ONLY JSON:
{
  "sprints": [{
    "id": "S-1",
    "name": string,
    "goal": string,
    "duration_days": number,
    "story_ids": string[],
    "tasks": [{ "id": "T-1", "title": string, "description": string, "story_points": number, "type": "frontend"|"backend"|"db"|"infra" }]
  }]
}\n\nPRD user stories:\n${JSON.stringify(prd.user_stories)}\n\nSystem design components:\n${JSON.stringify(design.components)}`,
    },
  ], true, "local");
  const plan = parseJson<SprintPlan>(res.content);
  return {
    artifact: plan,
    version: 1,
    steps: [
      {
        node: "sprint_plan",
        agent: "sprint_planner",
        input: { stories: prd.user_stories.length },
        output: plan,
        latency_ms: res.latency_ms,
        tokens_in: res.tokensIn,
        tokens_out: res.tokensOut,
      },
    ],
  };
}

// ---------- Stage 4: Build ----------
export async function runBuild(prd: PRD, design: SystemDesign): Promise<StageRunResult> {
  const res = await timed([
    {
      role: "system",
      content:
        "You are CoderAgent, a senior full-stack engineer. You write complete, runnable, well-structured code.",
    },
    {
      role: "user",
      content: `Write a complete, runnable codebase implementing this product. Focus on core functionality. Include 5-10 real files with full content.\n\nReturn ONLY JSON:
{
  "project_name": string,
  "tech_stack": string[],
  "files": [{ "path": string, "purpose": string, "content": string }]
}\n\nPRD:\n${JSON.stringify(prd)}\n\nDesign:\n${JSON.stringify(design)}`,
    },
  ], true, "gemini");
  const bundle = parseJson<CodeBundle>(res.content);
  return {
    artifact: bundle,
    version: 1,
    steps: [
      {
        node: "build",
        agent: "coder",
        input: { project: prd.title },
        output: { project_name: bundle.project_name, files: bundle.files.length },
        latency_ms: res.latency_ms,
        tokens_in: res.tokensIn,
        tokens_out: res.tokensOut,
      },
    ],
  };
}

// ---------- Stage 5: Test ----------
export async function runTest(bundle: CodeBundle): Promise<StageRunResult> {
  const filesSummary = bundle.files.map((f) => ({ path: f.path, purpose: f.purpose }));
  const res = await timed([
    {
      role: "system",
      content:
        "You are TesterAgent, a QA engineer. You write thorough pytest test suites.",
    },
    {
      role: "user",
      content: `Write a pytest test suite for this codebase. Include 3-6 test files with full Python source.\n\nReturn ONLY JSON:
{
  "framework": "pytest",
  "test_files": [{ "path": string, "content": string, "test_type": "unit"|"integration", "covers": string[] }]
}\n\nProject: ${bundle.project_name}\nTech stack: ${bundle.tech_stack.join(", ")}\nFiles:\n${JSON.stringify(filesSummary)}`,
    },
  ], true, "gemini");
  const suite = parseJson<TestSuite>(res.content);
  return {
    artifact: suite,
    version: 1,
    steps: [
      {
        node: "test",
        agent: "tester",
        input: { files: bundle.files.length },
        output: { test_files: suite.test_files.length },
        latency_ms: res.latency_ms,
        tokens_in: res.tokensIn,
        tokens_out: res.tokensOut,
      },
    ],
  };
}

export const GATED_STAGES: StageKey[] = ["plan", "design", "sprint_plan"];
