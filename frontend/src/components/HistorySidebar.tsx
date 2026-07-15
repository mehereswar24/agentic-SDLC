import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatRelativeTime } from "@/lib/utils";
import { Bot, Trash2, Clock, PanelLeftClose } from "lucide-react";
import { LiquidButton } from "@/components/ui/button";
import { api } from "@/lib/api";
function formatCompact(num: number) {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(num);
}

export function HistorySidebar({ onClose }: { onClose?: () => void }) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteRun(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const { data: runs } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.getRuns(),
    refetchInterval: 2000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.getStats(),
    refetchInterval: 5000,
  });

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="p-4 pt-6 border-b border-border shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="cursor-pointer" onClick={onClose} title="Close Sidebar">
              <LiquidButton
                size="icon"
                className="h-12 w-12 shrink-0 rounded-full shadow-lg"
              >
                <Bot className="h-6 w-6" />
              </LiquidButton>
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-bold tracking-tight text-foreground truncate">
                Agentic SDLC
              </h2>
              <p className="text-[10px] text-muted-foreground truncate">
                Orchestrator Control
              </p>
            </div>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] p-2 space-y-4">
        {stats && (
          <div className="flex flex-col">
            <div className="px-2 pb-2 text-xs font-medium text-muted-foreground">Overview</div>
            <div>
              <div className="grid grid-cols-2 gap-2 px-2 py-1">
                <div className="rounded-lg bg-surface-2 p-3 border border-border">
                  <p className="text-[10px] text-muted-foreground">Total Runs</p>
                  <p className="text-lg font-semibold">{stats.totalRuns}</p>
                </div>
                <div className="rounded-lg bg-surface-2 p-3 border border-border">
                  <p className="text-[10px] text-muted-foreground">Tokens</p>
                  <p className="text-lg font-semibold">{formatCompact(stats.totalTokens)}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-col">
          <div className="px-2 pb-2 text-xs font-medium text-muted-foreground">Recent History</div>
          <div className="flex flex-col gap-1 px-2">
            {runs?.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                No runs yet
              </div>
            ) : (
              runs?.map((run) => (
                <div key={run.id} className="w-full">
                  <Link
                    to="/runs/$runId"
                    params={{ runId: run.id }}
                    className="flex flex-col items-start gap-1 p-3 h-auto w-full rounded-md transition-colors hover:bg-surface-2 hover:text-foreground text-left text-sm"
                  >
                    <div className="flex items-center w-full justify-between">
                      <span className="text-xs font-medium truncate pr-4">
                        {run.prompt || "New Request"}
                      </span>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          deleteMutation.mutate(run.id);
                        }}
                        className="text-muted-foreground hover:text-red-500 hover:bg-red-500/10 p-1.5 rounded transition-colors"
                        title="Delete Run"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>{run.status}</span>
                      <span className="ml-1">•</span>
                      <span className="ml-1">
                        {new Date(run.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
