import { useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Boxes,
  KanbanSquare,
  Code2,
  FlaskConical,
  Edit3,
  Save,
  X,
  Loader2,
  HelpCircle,
  ShieldCheck,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { jsonToText } from "@/lib/artifact-text";
import type {
  ArtifactRow,
  ArtifactKind,
  ClarifyingQuestions,
  PRD,
  ReviewReport,
  RunStatus,
  SystemDesign,
  SprintPlan,
  CodeBundle,
  TestSuite,
  ValidationReport,
} from "@/lib/types";
import { PrdView, DesignView, SprintPlanView, CodeView, TestView } from "./artifacts";
import { VersionBar, type CompareSelection } from "./VersionBar";
import { ArtifactDiff } from "./ArtifactDiff";
import { ReviewReportCard } from "./ReviewReportCard";

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-border text-center">
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

const TABS = [
  { value: "clarifying_questions", label: "Questions", icon: HelpCircle },
  { value: "prd", label: "Requirements", icon: FileText },
  { value: "system_design", label: "Architecture", icon: Boxes },
  { value: "sprint_plan", label: "Sprint Plan", icon: KanbanSquare },
  { value: "code", label: "Codebase", icon: Code2 },
  { value: "test_suite", label: "Tests", icon: FlaskConical },
  { value: "reviews", label: "Reviews", icon: ShieldCheck },
] as const;

const EDITABLE: ArtifactKind[] = ["prd", "system_design", "sprint_plan", "code", "test_suite"];

function EditControls({
  artifact,
  runId,
  editing,
  setEditing,
  value,
  setValue,
}: {
  artifact: ArtifactRow;
  runId: string;
  editing: boolean;
  setEditing: (e: boolean) => void;
  value: string;
  setValue: (v: string) => void;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const handleSave = async () => {
    try {
      setBusy(true);
      await api.parseArtifact(runId, artifact.kind, value);
      toast.success("Artifact updated — new version created");
      qc.invalidateQueries({ queryKey: ["run", runId] });
      setEditing(false);
    } catch (err: any) {
      toast.error(err.message ?? "Failed to parse text");
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <button
        onClick={() => {
          setValue(jsonToText(artifact.content));
          setEditing(true);
        }}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
      >
        <Edit3 className="h-3.5 w-3.5" />
        Edit
      </button>
    );
  }
  return (
    <div className="flex gap-2">
      <button
        onClick={() => setEditing(false)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
      >
        <X className="h-3.5 w-3.5" />
        Cancel
      </button>
      <button
        onClick={handleSave}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        Save
      </button>
    </div>
  );
}

function ArtifactTab({
  kind,
  artifacts,
  runId,
  runStatus,
  emptyLabel,
  render,
}: {
  kind: ArtifactKind;
  artifacts: ArtifactRow[];
  runId: string;
  runStatus?: RunStatus;
  emptyLabel: string;
  render: (artifact: ArtifactRow) => React.ReactNode;
}) {
  const versions = useMemo(
    () =>
      artifacts
        .filter((a) => a.kind === kind)
        .sort((a, b) => a.version - b.version),
    [artifacts, kind],
  );
  const latest = versions[versions.length - 1];

  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [compare, setCompare] = useState<CompareSelection | null>(null);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  if (!latest) return <Empty label={emptyLabel} />;

  const selected =
    versions.find((v) => v.version === (selectedVersion ?? latest.version)) ?? latest;
  const isLatestSelected = selected.version === latest.version;
  // Backend rejects edits while the run is executing; hide Edit accordingly.
  const canEdit =
    EDITABLE.includes(kind) &&
    isLatestSelected &&
    !compare &&
    runStatus !== "running" &&
    runStatus !== "pending";

  const compareA = compare ? versions.find((v) => v.version === compare.a) : null;
  const compareB = compare ? versions.find((v) => v.version === compare.b) : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <VersionBar
          versions={versions}
          selected={selected.version}
          onSelect={(v) => {
            setSelectedVersion(v);
            setEditing(false);
          }}
          compare={compare}
          onCompare={(c) => {
            setCompare(c);
            setEditing(false);
          }}
        />
        <div className="ml-auto">
          {canEdit && (
            <EditControls
              artifact={latest}
              runId={runId}
              editing={editing}
              setEditing={setEditing}
              value={editValue}
              setValue={setEditValue}
            />
          )}
        </div>
      </div>

      {compare && compareA && compareB ? (
        <ArtifactDiff a={compareA} b={compareB} />
      ) : editing ? (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="min-h-[500px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          spellCheck={false}
        />
      ) : (
        <div>
          {!isLatestSelected && (
            <p className="mb-3 rounded-lg border border-border/60 bg-secondary/40 px-3 py-2 text-[11px] text-muted-foreground">
              Viewing v{selected.version} — an older version. Editing is only
              available on the latest version (v{latest.version}).
            </p>
          )}
          {render(selected)}
        </div>
      )}
    </div>
  );
}

function QuestionsView({ questions }: { questions: ClarifyingQuestions }) {
  return (
    <div className="space-y-5">
      {questions.inferred_scope && (
        <p className="rounded-xl border border-border/60 bg-secondary/40 p-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Inferred scope: </span>
          {questions.inferred_scope}
        </p>
      )}
      <div className="space-y-4">
        {questions.questions?.map((q) => (
          <div key={q.id} className="rounded-xl border border-border bg-card/50 p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
              {q.category}
            </div>
            <p className="mt-1 text-sm font-medium text-foreground">{q.question}</p>
            {q.options?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {q.options.map((o) => (
                  <span
                    key={o}
                    className="rounded-full border border-border bg-secondary px-2.5 py-0.5 text-[11px] text-muted-foreground"
                  >
                    {o}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {questions.assumptions?.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold text-foreground">Assumptions</div>
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground marker:text-muted-foreground/50">
            {questions.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ReviewsView({ artifacts }: { artifacts: ArtifactRow[] }) {
  const reviews = useMemo(() => {
    const byReviewer = new Map<string, ArtifactRow>();
    for (const a of artifacts) {
      if (a.kind !== "review_report") continue;
      const reviewer = String((a.content as any)?.reviewer ?? "reviewer");
      const existing = byReviewer.get(reviewer);
      if (!existing || a.version > existing.version) byReviewer.set(reviewer, a);
    }
    return [...byReviewer.values()];
  }, [artifacts]);

  const validations = useMemo(() => {
    const byKind = new Map<string, ArtifactRow>();
    for (const a of artifacts) {
      if (a.kind !== "validation_report") continue;
      const kind = String((a.content as any)?.artifact_kind ?? "artifact");
      const existing = byKind.get(kind);
      if (!existing || a.version > existing.version) byKind.set(kind, a);
    }
    return [...byKind.entries()];
  }, [artifacts]);

  if (reviews.length === 0 && validations.length === 0) {
    return <Empty label="No reviewer reports yet." />;
  }

  return (
    <div className="space-y-3">
      {reviews.map((a) => (
        <ReviewReportCard key={a.id} report={a.content as ReviewReport} />
      ))}
      {validations.map(([kind, a]) => {
        const v = a.content as ValidationReport;
        return (
          <div key={a.id} className="rounded-xl border border-border/60 bg-secondary/40 p-3.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-foreground">
                Semantic validation — {kind.replace(/_/g, " ")}
              </span>
              <span className="text-sm font-semibold tabular-nums text-foreground">
                {v.score}
                <span className="text-[10px] font-normal text-muted-foreground/70">/100</span>
              </span>
            </div>
            {v.issues?.length > 0 && (
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] text-muted-foreground marker:text-muted-foreground/50">
                {v.issues.map((i, idx) => (
                  <li key={idx}>{i}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ArtifactPanel({
  artifacts,
  runId,
  runStatus,
}: {
  artifacts: ArtifactRow[];
  runId: string;
  runStatus?: RunStatus;
}) {
  return (
    <Tabs defaultValue="prd" className="w-full">
      <TabsList className="glass flex h-auto w-full justify-start gap-1 overflow-x-auto rounded-2xl p-1.5 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {TABS.map((t) => (
          <TabsTrigger
            key={t.value}
            value={t.value}
            className="shrink-0 gap-1.5 rounded-xl px-3 py-2 text-xs data-[state=active]:bg-foreground data-[state=active]:text-background"
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>

      <div className="mt-4 glass-strong rounded-3xl p-6">
        <TabsContent value="clarifying_questions" className="mt-0">
          <ArtifactTab
            kind="clarifying_questions"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="No clarifying questions for this run."
            render={(a) => <QuestionsView questions={a.content as ClarifyingQuestions} />}
          />
        </TabsContent>
        <TabsContent value="prd" className="mt-0">
          <ArtifactTab
            kind="prd"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="Requirements not generated yet."
            render={(a) => <PrdView prd={a.content as PRD} />}
          />
        </TabsContent>
        <TabsContent value="system_design" className="mt-0">
          <ArtifactTab
            kind="system_design"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="Architecture not generated yet."
            render={(a) => <DesignView design={a.content as SystemDesign} />}
          />
        </TabsContent>
        <TabsContent value="sprint_plan" className="mt-0">
          <ArtifactTab
            kind="sprint_plan"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="Sprint plan not generated yet."
            render={(a) => <SprintPlanView plan={a.content as SprintPlan} />}
          />
        </TabsContent>
        <TabsContent value="code" className="mt-0">
          <ArtifactTab
            kind="code"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="Codebase not generated yet."
            render={(a) => <CodeView bundle={a.content as CodeBundle} runId={runId} />}
          />
        </TabsContent>
        <TabsContent value="test_suite" className="mt-0">
          <ArtifactTab
            kind="test_suite"
            artifacts={artifacts}
            runId={runId}
            runStatus={runStatus}
            emptyLabel="Test suite not generated yet."
            render={(a) => <TestView suite={a.content as TestSuite} />}
          />
        </TabsContent>
        <TabsContent value="reviews" className="mt-0">
          <ReviewsView artifacts={artifacts} />
        </TabsContent>
      </div>
    </Tabs>
  );
}
