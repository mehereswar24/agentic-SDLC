// Shared types for pipeline artifacts and entities. Client-safe.

export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_human"
  | "completed"
  | "failed";

export type StageKey = "plan" | "design" | "sprint_plan" | "build" | "test";

export type ArtifactKind =
  | "prd"
  | "system_design"
  | "sprint_plan"
  | "code"
  | "test_suite"
  | "critique";

export interface RunMeta {
  stage_index: number;
  awaiting_stage: StageKey | null;
  last_completed_stage: StageKey | null;
  auto_approve: boolean;
  max_revisions: number;
  feedback?: Record<string, string>;
}

export interface RunRow {
  id: string;
  prompt: string;
  status: RunStatus;
  error: string | null;
  meta: RunMeta;
  created_at: string;
  updated_at: string;
}

export interface AgentStepRow {
  id: string;
  run_id: string;
  node: string;
  agent: string;
  input: unknown;
  output: unknown;
  error: string | null;
  latency_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  created_at: string;
}

export interface ArtifactRow {
  id: string;
  run_id: string;
  kind: ArtifactKind;
  version: number;
  content: unknown;
  created_at: string;
}

// ---- Artifact content shapes ----

export interface UserStory {
  id: string;
  as_a: string;
  i_want: string;
  so_that: string;
  acceptance_criteria: string[];
}

export interface PRD {
  title: string;
  summary: string;
  problem_statement: string;
  goals: string[];
  non_goals: string[];
  personas: { name: string; description: string }[];
  user_stories: UserStory[];
  functional_requirements: string[];
  non_functional_requirements: string[];
  constraints: string[];
  risks: string[];
  success_metrics: string[];
}

export interface SystemDesign {
  overview: string;
  components: { name: string; technology: string; responsibility: string }[];
  data_models: { entity: string; purpose: string; key_fields: string[] }[];
  integration_points: string[];
}

export interface SprintTask {
  id: string;
  title: string;
  description: string;
  story_points: number;
  type: "frontend" | "backend" | "db" | "infra";
}

export interface Sprint {
  id: string;
  name: string;
  goal: string;
  duration_days: number;
  story_ids: string[];
  tasks: SprintTask[];
}

export interface SprintPlan {
  sprints: Sprint[];
}

export interface CodeFile {
  path: string;
  purpose: string;
  content: string;
}

export interface CodeBundle {
  project_name: string;
  tech_stack: string[];
  files: CodeFile[];
}

export interface TestFile {
  path: string;
  content: string;
  test_type: "unit" | "integration";
  covers: string[];
}

export interface TestSuite {
  framework: string;
  test_files: TestFile[];
}

export interface Critique {
  score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

export const STAGES: {
  key: StageKey;
  label: string;
  agent: string;
  gated: boolean;
  description: string;
}[] = [
  {
    key: "plan",
    label: "Plan",
    agent: "PlannerAgent",
    gated: true,
    description:
      "Drafts a full Product Requirements Document, then self-critiques and revises until the quality bar is met.",
  },
  {
    key: "design",
    label: "Design",
    agent: "DesignerAgent",
    gated: true,
    description:
      "Produces a lightweight system architecture — components, data models, and integration points.",
  },
  {
    key: "sprint_plan",
    label: "Sprint Plan",
    agent: "SprintPlannerAgent",
    gated: true,
    description:
      "Groups user stories into agile sprints with task breakdowns, story points, and types.",
  },
  {
    key: "build",
    label: "Build",
    agent: "CoderAgent",
    gated: false,
    description: "Writes a complete, runnable codebase from the requirements and design.",
  },
  {
    key: "test",
    label: "Test",
    agent: "TesterAgent",
    gated: false,
    description: "Generates a full pytest test suite covering the generated codebase.",
  },
];

export const ARTIFACT_FOR_STAGE: Record<StageKey, ArtifactKind> = {
  plan: "prd",
  design: "system_design",
  sprint_plan: "sprint_plan",
  build: "code",
  test: "test_suite",
};
