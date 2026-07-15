import { useState } from "react";

import { useQueryClient } from "@tanstack/react-query";
import { Check, X, MessageSquare, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { STAGES, type StageKey } from "@/lib/types";
import { LiquidButton } from "@/components/ui/button";

export function ApprovalGate({
  runId,
  stage,
}: {
  runId: string;
  stage: StageKey;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  const stageLabel = STAGES.find((s) => s.key === stage)?.label ?? stage;

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["run", runId] });
    qc.invalidateQueries({ queryKey: ["runs"] });
  };

  return (
    <div className="glass-strong float-in rounded-3xl p-6">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-background">
          <MessageSquare className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Review required — {stageLabel}
          </h3>
          <p className="text-xs text-muted-foreground">
            Approve to continue the pipeline, or reject to terminate this run.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4">
        <LiquidButton
          disabled={busy !== null}
          size="lg"
          variant="default"
          onClick={async () => {
            setBusy("approve");
            try {
              await api.decideRun(runId, { decision: "approve" });
              toast.success("Approved — resuming pipeline");
              refresh();
            } catch {
              toast.error("Failed to approve");
            } finally {
              setBusy(null);
            }
          }}
        >
          {busy === "approve" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          Approve &amp; continue
        </LiquidButton>
        <LiquidButton
          disabled={busy !== null}
          size="lg"
          variant="destructive"
          onClick={async () => {
            setBusy("reject");
            try {
              await api.decideRun(runId, { decision: "reject" });
              toast("Run terminated");
              refresh();
            } catch {
              toast.error("Failed to reject");
            } finally {
              setBusy(null);
            }
          }}
        >
          {busy === "reject" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <X className="h-4 w-4" />
          )}
          Reject &amp; terminate
        </LiquidButton>
      </div>
    </div>
  );
}
