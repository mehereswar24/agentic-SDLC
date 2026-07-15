import { useEffect, useRef } from "react";

/**
 * Run `fn` immediately and then every `intervalMs`, pausing while the tab is
 * hidden (and catching up the moment it becomes visible again) so background
 * tabs don't hammer the API.
 */
export function usePolling(fn: () => void | Promise<void>, intervalMs: number) {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;

    const tick = () => void fnRef.current();

    const start = () => {
      if (timer) return;
      tick();
      timer = setInterval(tick, intervalMs);
    };

    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };

    const onVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    document.addEventListener("visibilitychange", onVisibility);
    if (!document.hidden) start();

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
    };
  }, [intervalMs]);
}
