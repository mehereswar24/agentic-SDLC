import { useEffect, useState } from "react";
import { useTheme } from "@/lib/theme";

// Lazily-created singleton highlighter. Everything shiki lives behind a
// dynamic import inside useEffect, so nothing lands in the SSR graph or the
// entry chunk — grammars/themes load once, on first use of a code view.
let highlighterPromise: Promise<any> | null = null;

const LANGS = [
  "typescript",
  "tsx",
  "javascript",
  "jsx",
  "json",
  "python",
  "html",
  "css",
  "markdown",
  "yaml",
  "bash",
  "sql",
  "toml",
];

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      const { createHighlighter } = await import("shiki");
      return createHighlighter({
        themes: ["min-light", "min-dark"],
        langs: LANGS,
      });
    })();
  }
  return highlighterPromise;
}

/**
 * Returns highlighted HTML for `code`, or null while loading / for unknown
 * languages — callers render a plain <pre> fallback until it upgrades.
 * Client-only by construction (dynamic import inside useEffect), so SSR
 * renders the fallback and hydration stays stable.
 */
export function useShiki(code: string, lang: string | undefined): string | null {
  const { theme } = useTheme();
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    if (!lang || !code) return;

    getHighlighter()
      .then((hl) => {
        if (cancelled) return;
        if (!hl.getLoadedLanguages().includes(lang)) return;
        const out = hl.codeToHtml(code, {
          lang,
          theme: theme === "dark" ? "min-dark" : "min-light",
        });
        if (!cancelled) setHtml(out);
      })
      .catch(() => {
        /* highlighting is progressive enhancement — fall back silently */
      });

    return () => {
      cancelled = true;
    };
  }, [code, lang, theme]);

  return html;
}
