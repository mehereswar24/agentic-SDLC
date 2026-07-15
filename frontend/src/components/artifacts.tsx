import { useState } from "react";
import {
  FileText,
  Target,
  Users,
  ListChecks,
  ShieldAlert,
  Gauge,
  Boxes,
  Database,
  Plug,
  Copy,
  Check,
  Download,
  File as FileIcon,
  FlaskConical,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type {
  PRD,
  SystemDesign,
  SprintPlan,
  CodeBundle,
  TestSuite,
} from "@/lib/types";

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="float-in">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </div>
      <div className="text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((it, i) => (
        <span
          key={i}
          className="rounded-full border border-border bg-secondary px-2.5 py-1 text-xs text-secondary-foreground"
        >
          {it}
        </span>
      ))}
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items?.map((it, i) => (
        <li key={i} className="flex gap-2">
          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-foreground/50" />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

export function PrdView({ prd }: { prd: PRD }) {
  return (
    <div className="space-y-7">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">{prd.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{prd.summary}</p>
      </div>

      <Section icon={FileText} title="Problem statement">
        <p className="leading-relaxed">{prd.problem_statement}</p>
      </Section>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section icon={Target} title="Goals">
          <Bullets items={prd.goals} />
        </Section>
        <Section icon={Target} title="Non-goals">
          <Bullets items={prd.non_goals} />
        </Section>
      </div>

      <Section icon={Users} title="Target Users">
        <div className="space-y-2">
          {(prd.target_users || (prd as any).personas)?.map((p, i) => (
            <div key={i} className="rounded-xl border border-border bg-card/50 p-3">
              <div className="text-sm font-medium text-foreground">{p.name}</div>
              <div className="text-xs">{p.description}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={ListChecks} title="User stories">
        <div className="space-y-3">
          {prd.user_stories?.map((s) => (
            <div key={s.id} className="rounded-xl border border-border bg-card/50 p-4">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-foreground px-1.5 py-0.5 font-mono text-[10px] font-semibold text-background">
                  {s.id}
                </span>
              </div>
              <p className="mt-2 text-sm text-foreground">
                As a <b>{s.as_a}</b>, I want <b>{s.i_want}</b> so that {s.so_that}.
              </p>
              {s.acceptance_criteria?.length > 0 && (
                <div className="mt-2 space-y-2 border-l-2 border-border pl-3 text-xs">
                  {s.acceptance_criteria.map((ac, i) => (
                    <div key={i}>
                      <div><span className="font-semibold text-muted-foreground">Given</span> {typeof ac === 'string' ? ac : ac.given}</div>
                      {ac.when && <div><span className="font-semibold text-muted-foreground">When</span> {ac.when}</div>}
                      {ac.then && <div><span className="font-semibold text-muted-foreground">Then</span> {ac.then}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section icon={ListChecks} title="Functional requirements">
          <ul className="space-y-2">
            {prd.functional_requirements?.map((req, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <div className="flex gap-2 text-sm">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-foreground/50" />
                  <span className="font-medium text-foreground">{typeof req === 'string' ? req : req.statement}</span>
                </div>
                {typeof req !== 'string' && req.rationale && (
                  <span className="pl-3 text-xs text-muted-foreground">{req.rationale}</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={Gauge} title="Non-functional requirements">
          <ul className="space-y-2">
            {prd.non_functional_requirements?.map((req, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <div className="flex gap-2 text-sm">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-foreground/50" />
                  <span className="font-medium text-foreground">{typeof req === 'string' ? req : req.statement}</span>
                </div>
                {typeof req !== 'string' && req.category && (
                  <span className="pl-3 text-xs text-muted-foreground">Category: {req.category}</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section icon={ShieldAlert} title="Constraints">
          <Bullets items={prd.constraints} />
        </Section>
        <Section icon={ShieldAlert} title="Risks">
          <ul className="space-y-3">
            {prd.risks?.map((risk, i) => (
              <li key={i} className="flex flex-col gap-1 rounded-lg border border-border bg-card/50 p-3 text-sm">
                {typeof risk === 'string' ? (
                   <span>{risk}</span>
                ) : (
                  <>
                    <div className="font-medium text-foreground">{risk.description}</div>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      <span className="capitalize">Severity: {risk.severity}</span>
                      <span className="capitalize">Likelihood: {risk.likelihood}</span>
                    </div>
                    <div className="text-xs">Mitigation: {risk.mitigation}</div>
                  </>
                )}
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <Section icon={Gauge} title="Success metrics">
        <ul className="space-y-3 sm:grid sm:grid-cols-2 sm:space-y-0 sm:gap-4">
          {prd.success_metrics?.map((metric, i) => (
            <li key={i} className="flex flex-col gap-0.5 rounded-lg border border-border bg-card/50 p-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground text-sm">{typeof metric === 'string' ? metric : metric.name}</span>
              </div>
              {typeof metric !== 'string' && (
                <div className="mt-1 text-xs text-muted-foreground space-y-1">
                  <div><span className="font-medium">Target:</span> {metric.target}</div>
                  {metric.instrumentation && <div><span className="font-medium">Tracking:</span> {metric.instrumentation}</div>}
                </div>
              )}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

export function DesignView({ design }: { design: SystemDesign }) {
  return (
    <div className="space-y-7">
      <Section icon={Boxes} title="Architecture overview">
        <p className="leading-relaxed">{design.overview}</p>
      </Section>

      <Section icon={Boxes} title="Components">
        <div className="grid gap-3 sm:grid-cols-2">
          {design.components?.map((c, i) => (
            <div key={i} className="rounded-xl border border-border bg-card/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">{c.name}</span>
                <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-[10px]">
                  {c.technology}
                </span>
              </div>
              <p className="mt-1.5 text-xs">{c.responsibility}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={Database} title="Data models">
        <div className="space-y-3">
          {design.data_models?.map((m, i) => (
            <div key={i} className="rounded-xl border border-border bg-card/50 p-4">
              <div className="text-sm font-medium text-foreground">{m.entity}</div>
              <p className="mt-1 text-xs">{m.purpose}</p>
              <div className="mt-2">
                <Chips items={m.key_fields} />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={Plug} title="Integration points">
        <Bullets items={design.integration_points} />
      </Section>
    </div>
  );
}

const TYPE_STYLE: Record<string, string> = {
  frontend: "bg-foreground/90 text-background",
  backend: "bg-foreground/70 text-background",
  db: "bg-foreground/50 text-background",
  infra: "bg-secondary text-secondary-foreground",
};

export function SprintPlanView({ plan }: { plan: SprintPlan }) {
  return (
    <div className="space-y-5">
      {plan.sprints?.map((sprint) => {
        const points = sprint.tasks?.reduce((a, t) => a + (t.story_points ?? 0), 0) ?? 0;
        return (
          <div
            key={sprint.id}
            className="float-in rounded-2xl border border-border bg-card/50 p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-foreground px-1.5 py-0.5 font-mono text-[10px] font-semibold text-background">
                  {sprint.id}
                </span>
                <span className="text-base font-semibold text-foreground">{sprint.name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{sprint.duration_days}d</span>
                <span>{points} pts</span>
              </div>
            </div>
            <p className="mt-1.5 text-sm text-muted-foreground">{sprint.goal}</p>
            {sprint.story_ids?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {sprint.story_ids.map((id) => (
                  <span
                    key={id}
                    className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                  >
                    {id}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-3 space-y-2">
              {sprint.tasks?.map((t) => (
                <div
                  key={t.id}
                  className="flex items-start gap-3 rounded-xl border border-border bg-background/40 p-3"
                >
                  <span
                    className={cn(
                      "mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium",
                      TYPE_STYLE[t.type] ?? "bg-secondary",
                    )}
                  >
                    {t.type}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-foreground">{t.title}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {t.story_points} pts
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{t.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function download(name: string, content: string, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        toast.success("Copied to clipboard");
        setTimeout(() => setCopied(false), 1500);
      }}
      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function CodeView({ bundle }: { bundle: CodeBundle }) {
  const [active, setActive] = useState(0);
  const file = bundle.files?.[active];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-foreground">{bundle.project_name}</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {bundle.tech_stack?.map((t) => (
              <span
                key={t}
                className="rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px]"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
        <button
          onClick={() =>
            download(
              `${bundle.project_name.replace(/\s+/g, "-").toLowerCase()}-bundle.json`,
              JSON.stringify(bundle, null, 2),
              "application/json",
            )
          }
          className="inline-flex items-center gap-1.5 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background transition-opacity hover:opacity-90"
        >
          <Download className="h-3.5 w-3.5" />
          Download bundle
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <div className="glass max-h-[520px] overflow-auto rounded-2xl p-2">
          {bundle.files?.map((f, i) => (
            <button
              key={f.path}
              onClick={() => setActive(i)}
              className={cn(
                "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors",
                i === active
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              <FileIcon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate font-mono">{f.path}</span>
            </button>
          ))}
        </div>

        {file && (
          <div className="glass overflow-hidden rounded-2xl">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
              <div className="min-w-0">
                <div className="truncate font-mono text-xs text-foreground">{file.path}</div>
                <div className="truncate text-[11px] text-muted-foreground">{file.purpose}</div>
              </div>
              <div className="flex items-center gap-2">
                <CopyBtn text={file.content} />
                <button
                  onClick={() => download(file.path.split("/").pop() ?? "file.txt", file.content)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <pre className="max-h-[460px] overflow-auto p-4 font-mono text-xs leading-relaxed text-foreground">
              <code>{file.content}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export function TestView({ suite }: { suite: TestSuite }) {
  const [active, setActive] = useState(0);
  const file = suite.test_files?.[active];
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm">
        <FlaskConical className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium text-foreground">{suite.framework}</span>
        <span className="text-muted-foreground">· {suite.test_files?.length ?? 0} files</span>
      </div>

      <div className="grid gap-4 md:grid-cols-[240px_1fr]">
        <div className="glass max-h-[520px] overflow-auto rounded-2xl p-2">
          {suite.test_files?.map((f, i) => (
            <button
              key={f.path}
              onClick={() => setActive(i)}
              className={cn(
                "w-full rounded-lg px-2.5 py-2 text-left transition-colors",
                i === active ? "bg-foreground text-background" : "hover:bg-accent",
              )}
            >
              <div className="truncate font-mono text-xs">{f.path}</div>
              <div
                className={cn(
                  "mt-0.5 text-[10px]",
                  i === active ? "text-background/70" : "text-muted-foreground",
                )}
              >
                {f.test_type}
              </div>
            </button>
          ))}
        </div>

        {file && (
          <div className="glass overflow-hidden rounded-2xl">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
              <div className="min-w-0">
                <div className="truncate font-mono text-xs text-foreground">{file.path}</div>
                {file.covers?.length > 0 && (
                  <div className="truncate text-[11px] text-muted-foreground">
                    covers: {file.covers.join(", ")}
                  </div>
                )}
              </div>
              <CopyBtn text={file.content} />
            </div>
            <pre className="max-h-[460px] overflow-auto p-4 font-mono text-xs leading-relaxed text-foreground">
              <code>{file.content}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
