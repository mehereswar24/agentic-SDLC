// Tiny class-name joiner — the `cn` helper the 21st.dev / shadcn component
// API expects. We don't pull in clsx + tailwind-merge here because these
// components never pass conflicting Tailwind classes; a filtered join is enough.
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
