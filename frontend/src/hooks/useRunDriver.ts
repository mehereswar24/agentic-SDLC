import { useEffect } from "react";
import type { RunDetail } from "@/lib/types";

// Stubbed driver for Vite project. 
// The actual execution is driven by WebSockets in useRunStream.
export function useRunDriver(run: RunDetail | null | undefined) {
  useEffect(() => {
    if (!run) return;
    // Driver logic would go here if not using WebSockets
  }, [run]);
}
