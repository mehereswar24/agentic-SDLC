import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, RotateCw, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessage, RunStatus } from "@/lib/types";

const SUGGESTIONS = [
  "What's the current progress?",
  "Summarize the PRD.",
  "Why is this run waiting or blocked?",
  "What did the reviewers flag?",
];

export function RunChat({
  runId,
  status,
}: {
  runId: string;
  status?: RunStatus;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // NOTE: the parent renders this component with key={runId}, so navigating
  // to a different run remounts it and naturally resets all chat state.

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || loading) return;

    const history = messages;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const res = await api.chat(runId, { message: question, history });
      setMessages((m) => [...m, { role: "model", text: res.message }]);
    } catch (err) {
      const msg =
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Chat request failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  };

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-secondary text-foreground">
          <MessageSquare className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold leading-tight text-foreground">
            Ask about this run
          </h3>
          <p className="text-[11px] leading-tight text-muted-foreground/70">
            Grounded in this run's status, steps &amp; artifacts
          </p>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {empty && !loading ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
              Ask about progress, the PRD, design, code, errors, or why the run is
              waiting. Try one of these:
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => void send(s)}
                  className="rounded-full border border-border bg-secondary px-3 py-1.5 text-[11px] text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, idx) => (
            <div
              key={idx}
              className={cn(
                "flex",
                m.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-sm leading-relaxed",
                  m.role === "user"
                    ? "rounded-br-sm bg-foreground text-background"
                    : "rounded-bl-sm border border-border bg-secondary text-foreground",
                )}
              >
                {m.text}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-xl rounded-bl-sm border border-border bg-secondary px-3.5 py-2.5 text-xs text-muted-foreground">
              <RotateCw className="h-3.5 w-3.5 animate-spin" />
              Thinking…
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              const t = e.currentTarget;
              t.style.height = "auto";
              t.style.height = `${Math.min(t.scrollHeight, 128)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              status === "pending"
                ? "The run hasn't produced anything yet — ask once it's underway…"
                : "Ask a question… (Enter to send, Shift+Enter for newline)"
            }
            className="max-h-32 flex-1 resize-none rounded-lg border border-input bg-background p-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            onClick={() => void send(input)}
            disabled={loading || !input.trim()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-foreground text-background transition-opacity hover:opacity-90 disabled:opacity-40"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
