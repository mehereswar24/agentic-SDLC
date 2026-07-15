import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, RotateCw, XCircle } from "lucide-react";

import { api, ApiError } from "../lib/api";
import { cn } from "../lib/cn";
import type { ChatMessage, RunStatus } from "../lib/types";
import { MetalButton } from "@/components/ui/button";

const SUGGESTIONS = [
  "What's the current progress?",
  "Summarize the PRD.",
  "Why is this run waiting or blocked?",
  "What did the latest critique say?",
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
    <div className="card flex h-[480px] flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-accent-soft text-accent">
          <MessageSquare className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold leading-tight text-ink">
            Ask about this run
          </h3>
          <p className="text-[11px] leading-tight text-faint">
            Grounded in this run's status, steps &amp; artifacts
          </p>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {empty && !loading ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="max-w-xs text-xs leading-relaxed text-muted">
              Ask about progress, the PRD, design, code, errors, or why the run is
              waiting. Try one of these:
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => void send(s)}
                  className="rounded-full border border-line bg-surface-2 px-3 py-1.5 text-[11px] text-muted transition-colors hover:border-accent/40 hover:text-accent-ink"
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
                    ? "rounded-br-sm bg-accent text-white"
                    : "rounded-bl-sm border border-line bg-surface-2 text-body",
                )}
              >
                {m.text}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-xl rounded-bl-sm border border-line bg-surface-2 px-3.5 py-2.5 text-xs text-muted">
              <RotateCw className="h-3.5 w-3.5 animate-spin text-accent" />
              Thinking…
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-300">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-line p-3">
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
            className="field max-h-32 flex-1 resize-none p-2.5 text-sm"
          />
          <MetalButton
            onClick={() => void send(input)}
            disabled={loading || !input.trim()}
            variant="primary"
            className="h-10 w-10 shrink-0 p-0"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </MetalButton>
        </div>
      </div>
    </div>
  );
}
