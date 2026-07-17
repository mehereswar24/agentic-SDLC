import { useState } from "react";
import { MessageSquare, X } from "lucide-react";

import { RunChat } from "@/components/RunChat";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { useIsMobile } from "@/hooks/use-mobile";
import type { RunStatus } from "@/lib/types";

/**
 * Floating chat dock: a launcher button pinned bottom-right that opens the
 * grounded run chat in a glass panel (desktop) or a bottom sheet (mobile),
 * so the chat is usable while reading the timeline or an artifact.
 */
export function ChatDock({ runId, status }: { runId: string; status?: RunStatus }) {
  const [open, setOpen] = useState(false);
  const isMobile = useIsMobile();

  const launcher = (
    <button
      onClick={() => setOpen((o) => !o)}
      className="glass-strong fixed bottom-8 right-8 z-50 grid h-12 w-12 place-items-center rounded-full text-foreground shadow-lg transition-transform hover:scale-105"
      aria-label={open ? "Close run chat" : "Open run chat"}
      title="Chat about this run"
    >
      {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
    </button>
  );

  if (isMobile) {
    return (
      <>
        {launcher}
        <Drawer open={open} onOpenChange={setOpen}>
          <DrawerContent className="h-[75vh]">
            <RunChat key={runId} runId={runId} status={status} />
          </DrawerContent>
        </Drawer>
      </>
    );
  }

  return (
    <>
      {launcher}
      {open && (
        <div className="glass-strong float-in fixed bottom-24 right-8 z-50 flex h-[560px] w-[400px] flex-col overflow-hidden rounded-3xl shadow-xl">
          <RunChat key={runId} runId={runId} status={status} />
        </div>
      )}
    </>
  );
}
