import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileText, Boxes, KanbanSquare, Code2, FlaskConical, Edit3, Save, X, Loader2 } from "lucide-react";
import type { ArtifactRow, ArtifactKind } from "@/lib/types";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type {
  PRD,
  SystemDesign,
  SprintPlan,
  CodeBundle,
  TestSuite,
} from "@/lib/types";
import { PrdView, DesignView, SprintPlanView, CodeView, TestView } from "./artifacts";

function latest(artifacts: ArtifactRow[], kind: ArtifactKind): ArtifactRow | undefined {
  return artifacts
    .filter((a) => a.kind === kind)
    .sort((a, b) => b.version - a.version)[0];
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-border text-center">
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

const TABS = [
  { value: "prd", label: "Requirements", icon: FileText },
  { value: "system_design", label: "Architecture", icon: Boxes },
  { value: "sprint_plan", label: "Sprint Plan", icon: KanbanSquare },
  { value: "code", label: "Codebase", icon: Code2 },
  { value: "test_suite", label: "Tests", icon: FlaskConical },
] as const;

function jsonToText(obj: any, indent = 0): string {
  if (obj === null || obj === undefined) return "";
  if (typeof obj !== "object") return String(obj);
  
  let result = "";
  const spaces = "  ".repeat(indent);
  
  if (Array.isArray(obj)) {
    for (const item of obj) {
      if (typeof item === "object" && item !== null) {
        result += `${spaces}- ${jsonToText(item, indent + 1).trimStart()}`;
      } else {
        result += `${spaces}- ${item}\n`;
      }
    }
  } else {
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === "object" && value !== null) {
        result += `${spaces}${key}:\n${jsonToText(value, indent + 1)}`;
      } else {
        result += `${spaces}${key}: ${value}\n`;
      }
    }
  }
  return result;
}

function EditableArtifact({
  artifact,
  runId,
  children,
}: {
  artifact: ArtifactRow | undefined;
  runId: string;
  children: React.ReactNode;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState("");

  if (!artifact) return <>{children}</>;

  const handleSave = async () => {
    try {
      setBusy(true);
      await api.parseArtifact(runId, artifact.kind, value);
      toast.success("Artifact updated successfully");
      qc.invalidateQueries({ queryKey: ["artifacts", runId] });
      setEditing(false);
    } catch (err: any) {
      toast.error(err.message ?? "Failed to parse text");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <div className="mb-4 flex justify-end">
        {!editing ? (
          <button
            onClick={() => {
              setValue(jsonToText(artifact.content));
              setEditing(true);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Edit Document
          </button>
        ) : (
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
        )}
      </div>

      {editing ? (
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="min-h-[500px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-accent"
          spellCheck={false}
        />
      ) : (
        children
      )}
    </div>
  );
}

export function ArtifactPanel({ artifacts, runId }: { artifacts: ArtifactRow[], runId: string }) {
  const prd = latest(artifacts, "prd");
  const design = latest(artifacts, "system_design");
  const sprint = latest(artifacts, "sprint_plan");
  const code = latest(artifacts, "code");
  const tests = latest(artifacts, "test_suite");

  return (
    <Tabs defaultValue="prd" className="w-full">
      <TabsList className="glass flex h-auto w-full flex-wrap justify-start gap-1 rounded-2xl p-1.5">
        {TABS.map((t) => (
          <TabsTrigger
            key={t.value}
            value={t.value}
            className="gap-1.5 rounded-xl px-3 py-2 text-xs data-[state=active]:bg-foreground data-[state=active]:text-background"
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>

      <div className="mt-4 glass-strong rounded-3xl p-6">
        <TabsContent value="prd" className="mt-0">
          <EditableArtifact artifact={prd} runId={runId}>
            {prd ? <PrdView prd={prd.content as PRD} /> : <Empty label="Requirements not generated yet." />}
          </EditableArtifact>
        </TabsContent>
        <TabsContent value="system_design" className="mt-0">
          <EditableArtifact artifact={design} runId={runId}>
            {design ? <DesignView design={design.content as SystemDesign} /> : <Empty label="Architecture not generated yet." />}
          </EditableArtifact>
        </TabsContent>
        <TabsContent value="sprint_plan" className="mt-0">
          <EditableArtifact artifact={sprint} runId={runId}>
            {sprint ? <SprintPlanView plan={sprint.content as SprintPlan} /> : <Empty label="Sprint plan not generated yet." />}
          </EditableArtifact>
        </TabsContent>
        <TabsContent value="code" className="mt-0">
          <EditableArtifact artifact={code} runId={runId}>
            {code ? <CodeView bundle={code.content as CodeBundle} /> : <Empty label="Codebase not generated yet." />}
          </EditableArtifact>
        </TabsContent>
        <TabsContent value="test_suite" className="mt-0">
          <EditableArtifact artifact={tests} runId={runId}>
            {tests ? <TestView suite={tests.content as TestSuite} /> : <Empty label="Test suite not generated yet." />}
          </EditableArtifact>
        </TabsContent>
      </div>
    </Tabs>
  );
}
