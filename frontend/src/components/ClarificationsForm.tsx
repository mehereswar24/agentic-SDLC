import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { HelpCircle, Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ClarifyingQuestions } from "@/lib/types";
import { LiquidButton } from "@/components/ui/button";

/**
 * Rendered at the clarify gate: turns the ClarifyingQuestions artifact into a
 * form. Options become chip-selects (still editable), free-form questions get
 * a textarea. Submitting resumes the pipeline with the answers as planner
 * context.
 */
export function ClarificationsForm({
  runId,
  questions,
}: {
  runId: string;
  questions: ClarifyingQuestions;
}) {
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const required = questions.questions.filter((q) => q.required);
  const missing = required.filter((q) => !(answers[q.id] ?? "").trim());
  const canSubmit = missing.length === 0 && Object.keys(answers).length > 0;

  const setAnswer = (id: string, value: string) =>
    setAnswers((a) => ({ ...a, [id]: value }));

  const submit = async () => {
    const filled = Object.fromEntries(
      Object.entries(answers).filter(([, v]) => v.trim()),
    );
    if (Object.keys(filled).length === 0) return;
    setBusy(true);
    try {
      await api.submitClarifications(runId, filled);
      toast.success("Answers submitted — resuming pipeline");
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    } catch (e: any) {
      toast.error(e.message ?? "Failed to submit answers");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-strong float-in rounded-3xl p-6">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-background">
          <HelpCircle className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            A few questions before planning
          </h3>
          <p className="text-xs text-muted-foreground">
            Your answers guide the PRD. Required questions are marked.
          </p>
        </div>
      </div>

      {questions.inferred_scope && (
        <p className="mt-4 rounded-xl border border-border/60 bg-secondary/40 p-3 text-[12px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Inferred scope: </span>
          {questions.inferred_scope}
        </p>
      )}

      <div className="mt-4 space-y-5">
        {questions.questions.map((q) => (
          <div key={q.id}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
              {q.category}
            </div>
            <p className="mt-0.5 text-sm font-medium text-foreground">
              {q.question}
              {q.required && <span className="ml-1 text-destructive">*</span>}
            </p>
            {q.options.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setAnswer(q.id, opt)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-[11px] font-medium transition-colors",
                      answers[q.id] === opt
                        ? "border-foreground bg-foreground text-background"
                        : "border-border bg-secondary text-muted-foreground hover:border-foreground/40 hover:text-foreground",
                    )}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
            <textarea
              rows={q.options.length > 0 ? 1 : 2}
              value={answers[q.id] ?? ""}
              onChange={(e) => setAnswer(q.id, e.target.value)}
              placeholder={
                q.options.length > 0 ? "Pick an option or write your own…" : "Your answer…"
              }
              className="mt-2 w-full resize-none rounded-lg border border-input bg-background p-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        ))}
      </div>

      {questions.assumptions.length > 0 && (
        <div className="mt-5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
            Assumptions unless you say otherwise
          </div>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] text-muted-foreground marker:text-muted-foreground/50">
            {questions.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <LiquidButton size="lg" disabled={busy || !canSubmit} onClick={submit}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          Submit answers &amp; continue
        </LiquidButton>
        {missing.length > 0 && (
          <span className="text-[11px] text-muted-foreground/70">
            {missing.length} required question{missing.length === 1 ? "" : "s"} left
          </span>
        )}
      </div>
    </div>
  );
}
