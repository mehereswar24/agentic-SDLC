import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  Sparkles,
  ArrowRight,
  Activity,
  Cpu,
  Layers,
  Loader2,
  Trash2,
  Info,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import {
  useRuns,
  useStats,
  useRunsRealtime,
  createRun,
  deleteRun,
} from "@/lib/api.tanstack";
import { StatusBadge } from "@/components/StatusBadge";
import { STAGES } from "@/lib/types";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { LiquidButton } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Agentic SDLC Orchestrator" },
      {
        name: "description",
        content:
          "Turn a one-line brief into a full software delivery lifecycle — requirements, design, sprint plan, code, and tests — run by autonomous AI agents.",
      },
      { property: "og:title", content: "Agentic SDLC Orchestrator" },
      {
        property: "og:description",
        content: "Turn a one-line brief into a full software delivery lifecycle — requirements, design, sprint plan, code, and tests — run by autonomous AI agents.",
      },
    ],
  }),
  component: Dashboard,
});



function Dashboard() {
  useRunsRealtime();
  const navigate = useNavigate();
  const { data: runs } = useRuns();
  const { data: stats } = useStats();

  const [prompt, setPrompt] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [maxRevisions, setMaxRevisions] = useState(2);
  const [launching, setLaunching] = useState(false);

  const launch = async () => {
    if (!prompt.trim()) {
      toast.error("Describe what you'd like to build first");
      return;
    }
    setLaunching(true);
    try {
      const id = await createRun({ prompt: prompt.trim(), autoApprove, maxRevisions });
      toast.success("Run launched");
      navigate({ to: "/runs/$runId", params: { runId: id } });
    } catch {
      toast.error("Failed to launch run");
      setLaunching(false);
    }
  };

  const running = (stats?.byStatus.running ?? 0) + (stats?.byStatus.pending ?? 0);

  return (
    <div className="w-full min-h-screen px-4 py-12 flex flex-col items-center justify-center relative">
      <div className="w-full max-w-3xl mx-auto flex flex-col items-center float-in z-10">
        
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground mb-10 text-center">
          What would you like to build?
        </h1>

        <div className="relative w-full group mt-4">
          <div className="relative flex items-center w-full bg-white/30 dark:bg-black/30 backdrop-blur-2xl border border-white/50 dark:border-white/10 shadow-[0_8px_32px_rgba(31,38,135,0.15)] rounded-full p-2 pl-6 overflow-hidden transition-all duration-300 focus-within:bg-white/50 dark:focus-within:bg-black/50 focus-within:border-white/70 dark:focus-within:border-white/20">
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your product in a sentence or two..."
              className="flex-1 bg-transparent border-none outline-none ring-0 text-base md:text-lg px-4 py-3 md:py-4 placeholder:text-muted-foreground/60 text-foreground w-full min-w-0"
              onKeyDown={(e) => {
                if (e.key === 'Enter') launch();
              }}
            />
            <LiquidButton
              onClick={launch}
              disabled={launching}
              size="icon"
              className="h-10 w-10 md:h-12 md:w-12 rounded-full shrink-0 shadow-lg ml-2 mr-2"
            >
              {launching ? (
                <Loader2 className="h-4 w-4 md:h-5 md:w-5 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 md:h-5 md:w-5" />
              )}
            </LiquidButton>
          </div>
        </div>

        {/* Settings below the search bar */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-8 bg-surface/30 backdrop-blur-md px-8 py-4 rounded-full border border-line/30 text-sm shadow-sm transition-opacity duration-300 opacity-80 hover:opacity-100">
          <label className="flex items-center gap-3 cursor-pointer group">
            <Switch checked={autoApprove} onCheckedChange={setAutoApprove} />
            <span>
              <span className="font-medium text-foreground group-hover:text-foreground/70 transition-colors">Auto-approve gates</span>
            </span>
          </label>
          
          <div className="w-px h-6 bg-line/50 hidden sm:block"></div>

          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 whitespace-nowrap font-medium text-foreground">
              Max revisions
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button type="button" className="text-muted-foreground hover:text-foreground">
                    <Info className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>The maximum number of times an agent will revise its output based on feedback.</p>
                </TooltipContent>
              </Tooltip>
            </span>
            <Slider
              value={[maxRevisions]}
              onValueChange={(v) => setMaxRevisions(v[0])}
              min={0}
              max={4}
              step={1}
              className="w-24 md:w-32"
            />
            <span className="w-4 text-center tabular-nums text-muted-foreground font-medium">
              {maxRevisions}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
