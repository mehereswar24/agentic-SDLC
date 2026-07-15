export interface ChatMessage {
  role: "user" | "model";
  text: string;
}

export interface ChatRequest {
  message: string;
  history: ChatMessage[];
}

export interface ChatResponse {
  message: string;
}

export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_human"
  | "completed"
  | "failed"
  | "cancelled";

export type ArtifactKind =
  | "prd"
  | "clarifying_questions"
  | "research_notes"
  | "critique"
  | "system_design"
  | "code"
  | "sprint_plan"
  | "test_suite";

export interface CreateRunRequest {
  prompt: string;
  max_revisions: number;
  auto_approve: boolean;
}

export interface DecisionRequest {
  decision: "approve" | "reject";
  feedback?: string;
}

export interface RunSummary {
  id: string;
  prompt: string;
  status: RunStatus;
  error: string | null;
  meta: {
    stage_index?: number;
    max_revisions?: number;
    auto_approve?: boolean;
    awaiting_stage?: PipelineStage | null;
    last_completed_stage?: PipelineStage | null;
    feedback?: Record<string, string>;
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
}

export interface AgentStepView {
  id: string;
  node: string;
  agent: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string | null;
  latency_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  created_at: string;
}

export interface ArtifactView<T = unknown> {
  id: string;
  kind: ArtifactKind;
  version: number;
  content: T;
  created_at: string;
}

export interface RunDetail extends RunSummary {
  steps: AgentStepView[];
  artifacts: ArtifactView[];
}

export interface PRD {
  title: string;
  summary: string;
  problem_statement: string;
  goals: string[];
  non_goals: string[];
  target_users: Array<{ name: string; description: string; key_needs: string[] }>;
  user_stories: Array<{
    id: string;
    priority: string;
    as_a: string;
    i_want: string;
    so_that: string;
    acceptance_criteria: Array<{ given: string; when: string; then: string }>;
  }>;
  functional_requirements: Array<{ id: string; statement: string; rationale?: string | null }>;
  non_functional_requirements: Array<{ id: string; category: string; statement: string }>;
  constraints: string[];
  assumptions: string[];
  risks: Array<{ description: string; severity: string; likelihood: string; mitigation: string }>;
  open_questions: string[];
  success_metrics: Array<{ name: string; target: string; instrumentation?: string | null }>;
}

export interface Critique {
  score: number;
  summary: string;
  should_revise: boolean;
  issues: string[];
  suggestions: string[];
  iteration?: number;
}

export interface SystemDesign {
  title: string;
  overview: string;
  components: Array<{ name: string; responsibility: string; technology?: string }>;
  data_models: Array<{ entity: string; purpose: string; key_fields: string[] }>;
  integration_points: string[];
  open_design_questions: string[];
}

export interface CodeFile {
  path: string;
  purpose: string;
  content: string;
}

export interface CodeBundle {
  project_name: string;
  description: string;
  tech_stack: string[];
  files: CodeFile[];
  setup_instructions: string;
  next_steps: string[];
}

export interface Stats {
  total_runs: number;
  by_status: {
    pending: number;
    running: number;
    completed: number;
    failed: number;
    cancelled: number;
  };
  agent_steps: number;
  tokens_in_total: number;
  tokens_out_total: number;
  avg_step_latency_ms: number;
}

export interface WsEvent {
  type: string;
  run_id: string;
  payload: Record<string, unknown>;
  ts: string;
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

export type PipelineStage = "plan" | "design" | "sprint_plan" | "build" | "test";

export interface PipelineStageMeta {
  name: PipelineStage;
  label: string;
  description: string;
  artifact_kind: ArtifactKind;
}

export const PIPELINE_STAGES: PipelineStageMeta[] = [
  {
    name: "plan",
    label: "Plan",
    description: "Drafts a full Product Requirements Document.",
    artifact_kind: "prd"
  },
  {
    name: "design",
    label: "Design",
    description: "Produces a lightweight system architecture.",
    artifact_kind: "system_design"
  },
  {
    name: "sprint_plan",
    label: "Sprint Plan",
    description: "Groups user stories into agile sprints.",
    artifact_kind: "sprint_plan"
  },
  {
    name: "build",
    label: "Build",
    description: "Writes a complete, runnable codebase.",
    artifact_kind: "code"
  },
  {
    name: "test",
    label: "Test",
    description: "Generates a full test suite.",
    artifact_kind: "test_suite"
  }
];

export type StageKey = PipelineStage;
export const STAGES = PIPELINE_STAGES.map(s => ({ ...s, key: s.name }));


export type RunRow = RunSummary;
export type AgentStepRow = AgentStepView;
export type ArtifactRow = ArtifactView;
export type RunMeta = RunSummary['meta'];
export const ARTIFACT_FOR_STAGE: Record<string, ArtifactKind> = { plan: 'prd', design: 'system_design', sprint_plan: 'sprint_plan', build: 'code', test: 'test_suite' };

